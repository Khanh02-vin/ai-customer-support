/* Verify widget thực tế: mở /widget/, bấm nút, gửi câu hỏi, chờ reply. */
const puppeteer = require("puppeteer");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({ headless: "new", args: ["--no-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.goto("http://localhost:8005/widget/", { waitUntil: "networkidle0" });
  await sleep(500);
  await page.click("#acs-btn");                       // mở widget
  await sleep(500);
  const welcome = await page.$eval("#acs-msgs .acs-bot", (el) => el.textContent);
  console.log("welcome:", welcome);
  await page.screenshot({ path: "mockup/widget-open.png" });

  // Gửi câu hỏi KB → agent trả lời
  await page.type("#acs-input", "Chính sách bảo hành thế nào?");
  await page.click("#acs-send");
  await sleep(25000);                                 // agent + LLM
  const msgs = await page.$$eval(".acs-m", (els) => els.map((e) => e.textContent.slice(0, 90)));
  console.log("messages:", msgs);
  await page.screenshot({ path: "mockup/widget-chat.png" });

  // Câu thứ 2 → escalate
  await page.type("#acs-input", "Tôi muốn gặp nhân viên thật");
  await page.click("#acs-send");
  await sleep(20000);
  const last = await page.$$eval(".acs-m", (els) => els.map((e) => e.textContent.slice(0, 100)));
  console.log("after escalate:", last.slice(-2));

  console.log("console errors:", errors.length ? errors : "none");
  await browser.close();
})();
