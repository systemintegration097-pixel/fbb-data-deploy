import asyncio
import time
from playwright.async_api import async_playwright

URL = "https://181.176.242.2:28001/an-portal/framework/default.html#/_ngict-logical"
USER = "juanvs"
PASSWORD = "Jjvs*271202"

def format_mac_to_gpon_sn(mac):
    if not mac:
        return ""
    # Remove colons, dashes and convert to upper case
    clean_mac = mac.replace(":", "").replace("-", "").upper()
    if len(clean_mac) >= 8:
        # Return ZTEG + last 8 characters
        return "ZTEG" + clean_mac[-8:]
    return clean_mac

async def _async_query_onu_status(gpon_sn, olt):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--ignore-certificate-errors"]
        )
        try:
            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            # Navigate with timeout
            await page.goto(URL, timeout=30000)
            await asyncio.sleep(3)
            
            # Login
            if await page.locator("input#inputUserName").count() > 0:
                await page.fill("input#inputUserName", USER)
                await page.fill("input#inputCiphercode", PASSWORD)
                await page.locator("button#loginBut").click()
                
            await page.wait_for_selector("text='ONU Query'", timeout=20000)
            await asyncio.sleep(2)
            
            # Click ONU Query tab
            elements = await page.locator("a#an-onu-query").all()
            for el in elements:
                await el.click(force=True)
                
            # Wait for iframe to load
            await asyncio.sleep(6)
            frame = page.frame_locator("#page-mainIframe")
            
            # 1. Select 'ONU MAC/SN' in the first dropdown
            selects = await frame.locator("plx-select").all()
            if selects:
                await selects[0].click(force=True)
                await asyncio.sleep(1)
                await frame.locator("plx-option:has-text('ONU MAC/SN'), .plx-select-dropdown-item:has-text('ONU MAC/SN'), li:has-text('ONU MAC/SN')").first.click(force=True)
                await asyncio.sleep(0.5)
                
            # 2. Select 'NE Name' in the second dropdown
            selects = await frame.locator("plx-select").all()
            if len(selects) >= 2:
                await selects[1].click(force=True)
                await asyncio.sleep(1)
                await frame.locator("plx-option:has-text('NE Name'), .plx-select-dropdown-item:has-text('NE Name'), li:has-text('NE Name')").first.click(force=True)
                await asyncio.sleep(0.5)
                
            # 3. Fill the inputs
            inputs = await frame.locator("input.plx-input").all()
            if len(inputs) >= 2:
                await inputs[0].fill(gpon_sn)
                await inputs[1].fill(olt)
                
                # Click Query
                await frame.locator("button:has-text('Query')").first.click()
                await asyncio.sleep(5)
                
                # Extract rows using fast JS evaluate
                js_extract = """
                body => {
                    const rows = Array.from(body.querySelectorAll('.plx-table-body tr, tr'));
                    return rows.map(row => {
                        const cells = Array.from(row.querySelectorAll('td'));
                        return cells.map(c => c.innerText.trim());
                    }).filter(r => r.length > 0);
                }
                """
                all_rows = await frame.locator("body").evaluate(js_extract)
                
                # Filter out headers and metadatos
                matching_records = []
                for r in all_rows:
                    if len(r) >= 12 and r[0] != "No." and "Location" not in r:
                        matching_records.append({
                            "no": r[0],
                            "location": r[1],
                            "ne_name": r[2],
                            "ne_ip": r[3],
                            "port": r[4],
                            "onu_id": r[5],
                            "onu_name": r[6],
                            "config_type": r[7],
                            "actual_type": r[8],
                            "auth_mode": r[9],
                            "auth_value": r[10],
                            "mac_sn": r[11],
                            "software_version": r[12] if len(r) > 12 else ""
                        })
                        
                await browser.close()
                return {"success": True, "records": matching_records}
            else:
                await browser.close()
                return {"success": False, "error": "Could not find inputs in the ONU query iframe."}
                
        except Exception as e:
            try:
                await browser.close()
            except Exception:
                pass
            return {"success": False, "error": str(e)}

def query_onu_status_from_portal(mac, olt):
    gpon_sn = format_mac_to_gpon_sn(mac)
    if not gpon_sn:
        return {"success": False, "error": "Invalid MAC address provided."}
        
    print(f"Querying portal: GPON_SN={gpon_sn}, OLT={olt}", flush=True)
    return asyncio.run(_async_query_onu_status(gpon_sn, olt))
