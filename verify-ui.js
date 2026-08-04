/* Verify UI: login → dashboard, chụp 4 view, log lỗi console. */
const puppeteer = require("puppeteer");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({ headless: "new", args: ["--no-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto("http://localhost:8005/", { waitUntil: "networkidle0" });
  await page.screenshot({ path: "mockup/ui-login.png" });

  // Đăng nhập demo/demo1234
  await page.type("input[placeholder='Tên đăng nhập']", "demo");
  await page.type("input[type=password]", "demo1234");
  await page.click("form button");
  await sleep(3000);
  await page.screenshot({ path: "mockup/ui-overview.png" });

  const h1 = await page.$eval("h1", (el) => el.textContent);
  const stats = await page.$$eval(".stat-card", (els) => els.length);
  console.log("h1:", h1, "| stat cards:", stats);

  // Ticket view
  const items = await page.$$eval(".line-sidebar__item", (els) => els.length);
  console.log("sidebar items:", items);
  const clickNav = async (label) => {
    const handles = await page.$$(".line-sidebar__item");
    for (const h of handles) {
      const t = await h.evaluate((el) => el.textContent);
      if (t.includes(label)) { await h.click(); return; }
    }
  };
  await clickNav("Ticket"); await sleep(1500);
  await page.screenshot({ path: "mockup/ui-tickets.png" });

  await clickNav("Kiến thức"); await sleep(1500);
  await page.screenshot({ path: "mockup/ui-kb.png" });

  await clickNav("Cài đặt"); await sleep(1500);
  await page.screenshot({ path: "mockup/ui-settings.png" });

  console.log("console errors:", errors.length ? errors : "none");
  await browser.close();
})();
