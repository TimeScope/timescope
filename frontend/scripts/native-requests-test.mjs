import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const transpile = (source) =>
  ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
    },
  }).outputText;
const { SceneTransitions } = await import(
  "data:text/javascript;base64," +
    Buffer.from(
      transpile(
        fs.readFileSync(
          new URL("../src/scene-transitions.ts", import.meta.url),
          "utf8",
        ),
      ),
    ).toString("base64")
);
const source = fs.readFileSync(
  new URL("../src/main.ts", import.meta.url),
  "utf8",
);
const ast = ts.createSourceFile(
  "main.ts",
  source,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TS,
);
function find(predicate) {
  let result;
  function visit(node) {
    if (result) return;
    if (predicate(node)) result = node;
    else ts.forEachChild(node, visit);
  }
  visit(ast);
  return result;
}
const handler = find(
  (node) =>
    ts.isCallExpression(node) &&
    node.expression.getText(ast) === "listen" &&
    node.arguments[0]?.getText(ast) === '"engine-event"',
).arguments[1].getText(ast);
const functions = ["transitionIdle", "sceneIdle", "nativeRequestIdle"]
  .map((name) =>
    find((node) => ts.isFunctionDeclaration(node) && node.name?.text === name),
  )
  .filter(Boolean)
  .map((node) => node.getText(ast))
  .join("\n");
function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function bounded(work) {
  let timer;
  try {
    return await Promise.race([
      work,
      new Promise((_, reject) => {
        timer = setTimeout(
          () =>
            reject(Error("native command waited for future camera refinement")),
          1000,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
const turn = () => new Promise((resolve) => setImmediate(resolve));
function harness() {
  const cameraRefinement = deferred(),
    calls = [],
    responses = [];
  const transitions = new SceneTransitions();
  const context = vm.createContext({
    performance,
    setTimeout,
    clearTimeout,
    sceneTransitions: transitions,
    drainSceneEvents: async () => {},
    refreshWork: Promise.resolve(),
    sceneSyncWork: Promise.resolve(),
    cameraSaveWork: Promise.resolve(),
    flushSceneSync: async () => {},
    representationGoal: undefined,
    restoringScene: false,
    viewportDataRefresh: {
      generation: 1,
      drain: () => cameraRefinement.promise,
    },
    desktopRequests: Promise.resolve(),
    eventTimer: undefined,
    filterIntent: { flush: async () => {} },
    snapshot: { revision: 1, workspace_id: "original" },
    tab: "inspect",
    view: { snapshotIdle: async () => {}, captureConsistent: (read) => read() },
    captureAppWindow: async () => {
      calls.push("capture");
      return "data:image/png;base64,frame";
    },
    cancelSceneSync() {},
    liveViewRequest: async (kind) => {
      calls.push(kind);
      return { workspace: context.snapshot.workspace_id };
    },
    agentRequest: async (kind) => {
      calls.push(kind);
      return { playing: false };
    },
    call: async (kind, args) => {
      assert.equal(kind, "view_response");
      responses.push(args);
    },
  });
  vm.runInContext(
    transpile(`${functions}\nconst receive = ${handler};`),
    context,
  );
  return {
    context,
    transitions,
    calls,
    responses,
    dispatch(kind, expires = Date.now() + 15000) {
      context.event = {
        payload: {
          kind,
          request_id: kind,
          arguments: {},
          expires_at_ms: expires,
        },
      };
      vm.runInContext("receive(event)", context);
      return context.desktopRequests;
    },
    async close() {
      cameraRefinement.resolve();
      await context.desktopRequests;
    },
  };
}

test("actual native controls and status do not wait for continuing viewport refinement", async () => {
  const h = harness();
  try {
    for (const kind of [
      "view_navigate",
      "view_status",
      "view_playback",
      "view_profile",
      "view_wait",
      "view_scenario",
    ]) {
      await bounded(h.dispatch(kind));
      assert.equal(h.calls.at(-1), kind);
      assert.equal(h.responses.at(-1).error, undefined);
    }
  } finally {
    await h.close();
  }
});

test("native execution still waits for workspace restoration and already-started data publication", async () => {
  const h = harness(),
    restore = deferred(),
    publication = deferred();
  h.context.refreshWork = publication.promise;
  h.transitions.enqueue(async () => {
    await restore.promise;
    h.context.snapshot = { revision: 2, workspace_id: "reopened" };
  });
  try {
    const work = h.dispatch("view_status");
    await turn();
    assert.equal(h.calls.length, 0);
    restore.resolve();
    await turn();
    assert.equal(h.calls.length, 0);
    publication.resolve();
    await bounded(work);
    assert.equal(h.responses[0].result.workspace, "reopened");
  } finally {
    restore.resolve();
    publication.resolve();
    await h.close();
  }
});

test("an expired native command cannot steer the workspace after a queued restore", async () => {
  const h = harness(),
    restore = deferred();
  h.transitions.enqueue(() => restore.promise);
  try {
    const work = h.dispatch("view_navigate", Date.now() - 1);
    restore.resolve();
    await bounded(work);
    assert.equal(h.calls.length, 0);
    assert.match(h.responses[0].error, /expired before execution/);
  } finally {
    restore.resolve();
    await h.close();
  }
});

test("native commands retain response ordering while the camera keeps moving", async () => {
  const h = harness(),
    first = deferred();
  h.context.liveViewRequest = async (kind) => {
    h.calls.push(kind);
    await first.promise;
    return {};
  };
  try {
    h.dispatch("view_navigate");
    const second = h.dispatch("view_status");
    await turn();
    assert.deepEqual(h.calls, ["view_navigate"]);
    first.resolve();
    await bounded(second);
    assert.deepEqual(h.calls, ["view_navigate", "view_status"]);
    assert.deepEqual(
      h.responses.map((row) => row.request_id),
      ["view_navigate", "view_status"],
    );
  } finally {
    first.resolve();
    await h.close();
  }
});

test("native app capture joins current publication without requiring future camera loads to stop", async () => {
  const h = harness(),
    publication = deferred();
  h.context.refreshWork = publication.promise;
  try {
    const work = h.dispatch("capture");
    await turn();
    assert.equal(h.calls.length, 0);
    publication.resolve();
    await bounded(work);
    assert.equal(h.calls[0], "capture");
    assert.equal(h.responses[0].data_url, "data:image/png;base64,frame");
  } finally {
    publication.resolve();
    await h.close();
  }
});
