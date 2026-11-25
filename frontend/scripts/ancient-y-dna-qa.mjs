import assert from "node:assert/strict";
import path from "node:path";
import { withLocalApp } from "./local-browser.mjs";
import { revealDemo } from "./demo-picker.mjs";

await withLocalApp("ancient-y-dna", async ({ page, api, out, pass }) => {
  await page.setViewportSize({ width: 1680, height: 1050 });
  await page.click("#help");
  await page.click("#demo-datasets");
  await revealDemo(page, "ancient-y-dna");
  await page.screenshot({ path: path.join(out, "official-demo-picker.png") });
  await page.locator('[data-demo-preview="ancient-y-dna"]').first().click();
  await page.waitForFunction(
    () =>
      window.__chronoscope?.snapshot?.count === 1708 &&
      !window.__chronoscope.busy,
  );
  const time = await api("snapshot", { compact: true });
  assert.equal(time.visible, 964);
  assert.equal(time.scene.mode, "space-time");
  assert.equal((await api("workspace_status")).source, null);
  pass(
    "Official picker opens the credited Eurasian demo in its saved regional Time view",
  );

  await page.evaluate(async () => {
    const c = window.__chronoscope;
    const r = await c.call("restore_view", { index: 9 });
    await c.restoreScene(r.scene);
  });
  assert.equal((await api("snapshot", { compact: true })).visible, 1031);
  const records = (await api("events", { limit: 20 })).events;
  assert(records.every((e) => e.attrs.y_assignment_tree === "AADR v66.p1 / ISOGG v15.73"));
  pass("The full demo retains its consistent AADR nomenclature subset");
});
