import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = fs.readFileSync(
  new URL("../src/resident-playback.ts", import.meta.url),
  "utf8",
);
const ast = ts.createSourceFile(
  "resident-playback.ts",
  source,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TS,
);
const klass = ast.statements.find((node) => ts.isClassDeclaration(node));
const method = klass.members
  .find((node) => node.name?.getText(ast) === "prepare")
  .getText(ast);
const code = ts.transpileModule(`const prepare = ({ ${method} }).prepare;`, {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness(readyAfter = Infinity) {
  let now = 0,
    renders = 0;
  const primitive = { ready: false };
  const target = {
    scene: { isDestroyed: () => false },
    epoch: 0,
    span: 1,
    preparationMs: 0,
    primitives: [primitive],
    uploads: [() => {}],
    setWindow() {},
  };
  const context = vm.createContext({
    performance: { now: () => now },
    setTimeout(resolve, milliseconds) {
      now += milliseconds;
      queueMicrotask(resolve);
    },
  });
  vm.runInContext(code, context);
  const prepare = vm.runInContext("prepare", context);
  return {
    run: (accept = () => true) =>
      prepare.call(target, accept, () => {
        if (++renders >= readyAfter) primitive.ready = true;
      }),
    elapsed: () => now,
    renders: () => renders,
  };
}

test("stalled GPU uploads fail early enough for standard playback before the native 15-second deadline", async () => {
  const h = harness();
  await assert.rejects(h.run(), /Prepared graphics timed out/);
  assert(
    h.elapsed() < 15000,
    `optional GPU warm-up occupied ${h.elapsed()} ms`,
  );
});

test("responsive uploads still prepare normally and cancelled preparation stops requesting frames", async () => {
  const ready = harness(3);
  assert.equal(await ready.run(), true);
  assert.equal(ready.renders(), 3);
  const cancelled = harness();
  assert.equal(await cancelled.run(() => false), false);
  assert.equal(cancelled.renders(), 0);
});
