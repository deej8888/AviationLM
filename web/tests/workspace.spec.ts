import { test, expect } from "@playwright/test";

test("extracts a request through the actual API and exposes validated JSON", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Extract request", exact: true })
    .click();
  await expect(page.getByText("Validated", { exact: true })).toBeVisible();
  await expect(page.getByText("TEB", { exact: true })).toBeVisible();
  await expect(page.getByText("MIA", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Citation Latitude", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Review before operational use", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "JSON", exact: true }).click();
  await expect(page.locator(".json-view")).toContainText('"passengers": 6');
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
  await expect(page.getByText("94.5%", { exact: true })).toBeVisible();
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
