import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { Cartesian3, Cartographic, PolylinePipeline } from "cesium";
import { withLocalApp } from "./local-browser.mjs";

await withLocalApp("spectate", async ({ page, api, out, pass }) => {
  const csv = path.join(out, "tracks.csv");
  fs.writeFileSync(csv, [
    "entity,timestamp,latitude,longitude",
    "Survey,2026-11-15T01:00:00Z,0,170",
    "Survey,2026-11-15T02:00:00Z,0,-170",
    "Survey,2026-11-15T03:00:00Z,10,-170",
    "Single,2026-11-15T01:00:00Z,2,0",
    "Diagonal,2026-11-15T01:15:00Z,10,165",
    "Diagonal,2026-11-15T02:30:00Z,45,-173",
  ].join("\n"));
  const preview = await api("import_preview", { path: csv });
  await api("import_commit", { import_id: preview.import_id });
  await page.evaluate(() => window.__chronoscope.refresh());
  await page.locator('[data-view="map"]').click();
  await page.evaluate(() => window.__chronoscope.viewModeIdle());

  const row = (entity) => page.locator("#entities .entity").filter({ has: page.getByText(entity, { exact: true }) });
  const menuItem = (name) => page.getByRole("menuitem", { name, exact: true });
  await row("Single").click({ button: "right" });
  await menuItem("Spectate").click();
  await page.getByText("Spectate needs at least two located events at different times.").waitFor();
  assert(await page.locator('[data-view="map"]').evaluate((button) => button.classList.contains("active")));

  const start = Date.parse("2026-11-15T01:15:00Z") / 1000;
  const endTime = Date.parse("2026-11-15T02:30:00Z") / 1000;
  await api("filter", { filter: { start, end: endTime } });
  await page.evaluate(() => window.__chronoscope.refresh());
  const setRate = (speed) => page.evaluate((speed) =>
    window.__chronoscope.liveViewRequest("view_playback", {
      action: "configure", speed, increment_seconds: 3600,
    }), speed);
  await setRate(0.25);
  await row("Survey").click({ button: "right" });
  await menuItem("Spectate").click();
  await page.getByRole("button", { name: "Stop spectating Survey" }).waitFor();
  const reading = () => page.evaluate(() => ({
    offset: window.__chronoscope.view.spectate.offset, wall: performance.now(),
  }));
  const first = await reading();
  assert(first.offset >= 0 && first.offset < 450);
  await page.waitForTimeout(350);
  const second = await reading();
  assert(Math.abs((second.offset - first.offset) / (second.wall - first.wall) - 0.9) < 0.18);
  assert(await page.locator('[data-view="globe"]').evaluate((button) => button.classList.contains("active")));
  assert(await page.locator("#navigation-zoom").isDisabled());

  const position = () => page.evaluate(() => {
    const { camera } = window.__chronoscope.view;
    const { latitude, longitude, height } = camera.positionCartographic;
    return { lat: latitude * 180 / Math.PI, lon: longitude * 180 / Math.PI, height, heading: camera.heading };
  });
  await page.waitForFunction(() => window.__chronoscope.view.spectate.offset >= 900);
  const crossing = await position();
  assert(Math.abs(crossing.lat) < 1e-6 && Math.abs(crossing.lon) > 179, JSON.stringify(crossing));
  await setRate(2);
  const atEnd = () => {
    const { offset, duration } = window.__chronoscope.view.spectate;
    return offset === duration;
  };
  await page.waitForFunction(atEnd, undefined, { timeout: 2000 });
  const end = await position();
  assert(Math.abs(end.lat - 5) < 0.001 && Math.abs(end.lon + 170) < 1e-6, JSON.stringify(end));
  await page.locator(".cesium-widget canvas").focus();
  await page.keyboard.press("KeyS");
  await page.waitForFunction(() => window.__chronoscope.view.spectate.offset === 0);
  const reversed = await position();
  assert(Math.abs(reversed.lat) < 1e-6 && Math.abs(reversed.lon - 175) < 1e-6, JSON.stringify(reversed));
  await page.keyboard.press("KeyW");
  await page.waitForFunction(atEnd, undefined, { timeout: 2000 });
  pass("Spectate uses the selected time window and playback rate in both directions, including across the date line");

  const hold = async (key) => {
    await page.keyboard.down(key);
    await page.waitForTimeout(250);
    await page.keyboard.up(key);
  };
  for (const key of ["KeyA", "KeyD", "ControlLeft"]) await hold(key);
  assert(Math.abs((await position()).height - end.height) < 0.001);
  await hold("Space");
  const risen = await position();
  await hold("Shift");
  const lowered = await position();
  assert(risen.height > end.height + 1 && lowered.height < risen.height - 1);
  const canvas = page.locator(".cesium-widget canvas");
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 20);
  const looked = await position();
  assert(Math.abs(looked.heading - end.heading) > 0.05);
  for (const pose of [risen, lowered, looked]) {
    assert(Math.abs(pose.lat - end.lat) < 1e-6);
    assert(Math.abs(pose.lon - end.lon) < 1e-6);
  }
  await page.evaluate(() => window.__chronoscope.view.stepGlobeFlight(0, 0, -10000));
  const floor = await position();
  assert(Math.abs(floor.height - 2) < 0.001);
  await hold("Space");
  assert((await position()).height > floor.height + 0.1);
  await page.keyboard.press("Escape");
  assert(await page.locator("#spectate-status").isHidden());
  assert(await page.locator("#navigation-zoom").isEnabled());
  assert.equal(await page.evaluate(() => window.__chronoscope.view.flightActive), false);
  pass("Spectate locks horizontal flight and zoom, permits height and free look, and exits on Escape");

  await row("Survey").locator("[data-select-entity]").focus();
  await page.keyboard.press("Shift+F10");
  await menuItem("Spectate").press("Enter");
  await page.getByRole("button", { name: "Stop spectating Survey" }).waitFor();
  await row("Survey").click({ button: "right" });
  await menuItem("Stop spectating").click();
  assert(await page.locator("#spectate-status").isHidden());
  pass("The keyboard-accessible entity menu can start and stop Spectate");

  await page.locator('[data-view="space-time"]').click();
  await page.evaluate(() => window.__chronoscope.viewModeIdle());
  await setRate(0.25);
  await row("Survey").click({ button: "right" });
  await menuItem("Spectate").click();
  await page.getByRole("button", { name: "Stop spectating Survey" }).waitFor();
  assert.equal(await page.evaluate(() => window.__chronoscope.view.mode), "space-time");
  await page.waitForFunction(() => window.__chronoscope.view.spectate.offset >= 900);
  const projectedCrossing = await position();
  assert(Math.abs(projectedCrossing.lat) < 1e-6 && Math.abs(projectedCrossing.lon) > 175, JSON.stringify(projectedCrossing));
  await setRate(2);
  await page.waitForFunction(atEnd, undefined, { timeout: 2000 });
  const timeEnd = await position();
  assert(Math.abs(timeEnd.lat - 5) < 1e-6 && Math.abs(timeEnd.lon + 170) < 1e-6);
  const timeHeight = await page.evaluate(() => window.__chronoscope.view.timeHeightMeters);
  assert(timeHeight > 0 && Math.abs(timeEnd.height - 122) < 0.01, JSON.stringify(timeEnd));
  await page.keyboard.press("KeyS");
  await page.waitForFunction(() => window.__chronoscope.view.spectate.offset === 0);
  const timeStart = await position();
  const early = Cartesian3.fromDegrees(170, 0, 2 + timeHeight);
  const middle = Cartesian3.fromDegrees(-170, 0, 2 + timeHeight * (1800 / (endTime - start)));
  const earlySplit = early.y / (early.y - middle.y);
  const startLongitude = 170 + 10 * (0.25 / earlySplit);
  assert(Math.abs(timeStart.lat) < 1e-6 && Math.abs(timeStart.lon - startLongitude) < 1e-6, JSON.stringify(timeStart));
  assert(Math.abs(timeStart.height - (122 + timeHeight)) < 0.01, JSON.stringify(timeStart));
  await page.evaluate(() => {
    const height = document.querySelector("#time-height");
    height.value = "1";
    height.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const scaled = await page.evaluate(() => ({
    height: window.__chronoscope.view.timeHeightMeters,
    offset: window.__chronoscope.view.spectate.offset,
  }));
  assert(scaled.height < timeHeight && scaled.offset === 0);
  assert(Math.abs((await position()).height - (122 + scaled.height)) < 0.01);
  await page.keyboard.press("KeyW");
  await page.waitForFunction(atEnd, undefined, { timeout: 2000 });
  await hold("Space");
  const timeRaised = await position();
  assert(timeRaised.height > timeEnd.height + 1 && Math.abs(timeRaised.lon - timeEnd.lon) < 1e-6);
  await page.keyboard.down("Shift");
  try {
    await page.waitForFunction(
      (height) => window.__chronoscope.view.camera.positionCartographic.height < height - 1,
      timeRaised.height,
      { timeout: 2000 },
    );
  } finally {
    await page.keyboard.up("Shift");
  }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 20);
  assert(Math.abs((await position()).heading - timeEnd.heading) > 0.05);
  await page.keyboard.press("Escape");
  assert(await page.locator("#spectate-status").isHidden());
  assert.equal(await page.evaluate(() => window.__chronoscope.view.mode), "space-time");
  pass("Time Spectate follows projected tracks and Time Height, with both directions, elevation, and mouse look");

  await page.evaluate(() => window.__chronoscope.view.setTimeAltitude(true));
  await row("Survey").click({ button: "right" });
  await menuItem("Spectate").click();
  await page.getByText("Spectate in Altitude mode needs two events with usable heights at different times.").waitFor();
  assert(await page.locator("#spectate-status").isHidden());
  await page.evaluate(() => window.__chronoscope.view.setTimeAltitude(false));

  await setRate(0.25);
  await row("Diagonal").click({ button: "right" });
  await menuItem("Spectate").click();
  await page.getByRole("button", { name: "Stop spectating Diagonal" }).waitFor();
  const heights = await page.evaluate(() => {
    const view = window.__chronoscope.view;
    return [view.timeHeightMeters + 2, 2];
  });
  const a = Cartesian3.fromDegrees(165, 10, heights[0]);
  const b = Cartesian3.fromDegrees(-173, 45, heights[1]);
  const { positions } = PolylinePipeline.wrapLongitude([a, b]);
  const seam = Cartographic.fromCartesian(positions[2]);
  const fraction = a.y / (a.y - b.y);
  await page.evaluate((fraction) => {
    const view = window.__chronoscope.view;
    const flight = view.spectate;
    flight.clock.setSpeed(0);
    flight.elapsed = flight.clock.seconds();
    flight.offset = flight.duration * (fraction + 1e-7);
    view.stepGlobeFlight(0, 0, 0, 0.01);
  }, fraction);
  const diagonal = await position();
  assert(Math.abs(diagonal.lat - seam.latitude * 180 / Math.PI) < 1e-4, JSON.stringify(diagonal));
  assert(diagonal.lon < -179.99, JSON.stringify(diagonal));
  await page.keyboard.press("Escape");
  pass("Altitude Spectate excludes missing heights and diagonal Time tracks use Cesium's date-line seam");
});
