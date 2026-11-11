import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("extracts a request through the actual API and exposes validated JSON", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Extract request", exact: true })
    .click();
  await expect(page.getByText("Validated", { exact: true })).toBeVisible();
  const output = page.getByRole("region", { name: "Extraction result" });
  await expect(output.getByText("TEB", { exact: true })).toBeVisible();
  await expect(output.getByText("MIA", { exact: true })).toBeVisible();
  await expect(
    output.getByText("Citation Latitude", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Review before operational use", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "JSON", exact: true }).click();
  await expect(page.locator(".json-view")).toContainText('"passengers": 6');
  await expect(page.getByRole("button", { name: "Download JSON" })).toBeDisabled();
  await page.getByLabel("I reviewed the extracted and missing details against the request.").check();
  await page.getByRole("button", { name: "Confirm review", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download JSON", exact: true })
    .click();
  expect((await downloadPromise).suggestedFilename()).toBe(
    "aerolm-extraction.json",
  );
  await page.getByRole("tab", { name: "Overview", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: info.outputPath("workspace.png"),
    fullPage: true,
  });
});

test("allows corrections, rechecks them, and invalidates prior confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Extract request", exact: true }).click();
  await expect(page.getByLabel("Leg 1 destination")).toHaveValue("MIA");
  await page.getByLabel("Leg 1 destination").fill("KBOB");
  await page.getByLabel("Passengers", { exact: true }).fill("8");
  await expect(page.getByRole("button", { name: "Download JSON" })).toBeDisabled();
  await page.getByRole("button", { name: "Check changes" }).click();
  await expect(page.getByText("KBOB was not found in the airport reference", { exact: false }).first()).toBeVisible();
  await page.getByLabel("I reviewed the extracted and missing details against the request.").check();
  await page.getByRole("button", { name: "Confirm review", exact: true }).click();
  await expect(page.getByRole("button", { name: "Download JSON" })).toBeEnabled();
  const event = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download JSON" }).click();
  const downloaded = await event;
  const content = JSON.parse(await readFile((await downloaded.path())!, "utf8"));
  expect(content.data.legs[0].destination).toBe("KBOB");
  expect(content.data.passengers).toBe(8);
  expect(content.original_data.passengers).toBe(6);
  expect(content.review.status).toBe("confirmed_by_user");
  expect(content.review.modified).toBe(true);
  await page.getByLabel("Passengers", { exact: true }).fill("9");
  await expect(page.getByRole("button", { name: "Download JSON" })).toBeDisabled();
});

test("clears stale output and handles ambiguity without guessed airports", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Start with an example")).toBeEnabled();
  await page.getByLabel("Start with an example").selectOption("ambiguous");
  await page
    .getByRole("button", { name: "Extract request", exact: true })
    .click();
  await expect(
    page.getByText("No airport route identified.", { exact: false }),
  ).toBeVisible();
  await page.getByLabel("REQUEST BODY", { exact: true }).fill(" ");
  await expect(
    page.getByRole("button", { name: "Extract request", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText("Validated", { exact: true })).not.toBeVisible();
});

test("shows actual benchmarks and pipeline on both viewports", async ({
  page,
}, info) => {
  await page.goto("/");
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Evaluations", exact: true }).click();
  await expect(
    page.getByText("rules-challenge", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("row").filter({ has: page.getByText("rules-challenge", { exact: true }) }).getByText("94.5%", { exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Schema valid", exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Exact request", exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("benchmarks.png"), fullPage: true, animations: "disabled" });
  if (info.project.name === "mobile") {
    const comparison = page.getByRole("region", { name: "Benchmark comparison", exact: false });
    await comparison.evaluate((element) => { element.scrollLeft = element.scrollWidth; });
    await expect(page.getByRole("columnheader", { name: "Nulls filled", exact: true })).toBeInViewport();
  }
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "The pipeline", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Charter first. Extensible by design." }),
  ).toBeVisible();
});

test("surfaces backend failures without inventing a result", async ({
  page,
}) => {
  await page.route("**/api/proxy/v1/extract", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Inference busy; retry shortly" }),
    }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Extract request", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Inference busy" }),
  ).toHaveText("Inference busy; retry shortly");
  await expect(page.getByText("Validated", { exact: true })).not.toBeVisible();
});
