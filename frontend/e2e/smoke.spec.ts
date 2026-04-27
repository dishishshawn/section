import { test, expect } from "@playwright/test";

/**
 * Smoke e2e: pretend we already have a session cookie, create a project via
 * the API, then open the UI and assert the runsheet heading is visible.
 *
 * Requires the backend running at http://localhost:8000 and the frontend at
 * http://localhost:3000. Uses SECTION_SESSION_COOKIE env var for the cookie.
 */
test("sign-in via stubbed cookie, create project, see runsheet", async ({
  page,
  context,
  baseURL,
  request,
}) => {
  const sessionCookie = process.env.SECTION_SESSION_COOKIE;
  test.skip(!sessionCookie, "Set SECTION_SESSION_COOKIE to run the smoke e2e.");

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  const uiBase = baseURL || "http://localhost:3000";

  await context.addCookies([
    {
      name: "section_session",
      value: sessionCookie!,
      url: uiBase,
      httpOnly: true,
    },
    {
      name: "section_session",
      value: sessionCookie!,
      url: apiBase.replace(/\/api$/, ""),
      httpOnly: true,
    },
  ]);

  const res = await request.post(`${apiBase}/projects`, {
    data: { name: "Smoke Project", jurisdiction: "TX" },
    headers: { Cookie: `section_session=${sessionCookie}` },
  });
  expect(res.ok()).toBeTruthy();
  const { id } = await res.json();

  await page.goto(`${uiBase}/projects/${id}`);
  await expect(page.getByRole("heading", { name: /runsheet/i })).toBeVisible({
    timeout: 10000,
  });
});
