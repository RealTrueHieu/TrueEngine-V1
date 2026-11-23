#!/usr/bin/env python3
"""
TrueEngine V1: Autonomous Molab Marimo REST API Server
======================================================
Provides a programmatic REST API for Molab (molab.marimo.io):
- Automatically provisions new virtual machines with RTX Pro 6000 Blackwell GPU
- Bootstraps the terminal via '!sudo apt install fastfetch' cell execution & syntax trigger
- Clicks 'Open terminal' and manages bash execution inside the remote VM
- Direct xterm buffer readback via React Fiber reflection
- Deploys and monitors the TrueEngine Blackwell Supercluster neural engine
- Zero manual browser clicks required!
"""

import os
import sys
import time
import asyncio
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
import uvicorn
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MolabAPI")

CDP_URL = "http://localhost:9222"
PORT = 8766

def get_hf_token():
    token = os.getenv("HF_TOKEN")
    if token:
        return token
    for p in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.expanduser("~/.cache/huggingface/token"),
        os.path.expanduser("~/.huggingface/token"),
    ]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("HF_TOKEN="):
                            return line.strip().split("=", 1)[1].strip("\"'")
                        elif not line.startswith("#") and line.strip().startswith("hf_"):
                            return line.strip()
            except Exception:
                pass
    return ""

HF_TOKEN = get_hf_token()

app = FastAPI(
    title="Molab Marimo Autonomous Virtual Machine API",
    description="Custom programmatic REST API for creating and orchestrating Molab Blackwell VMs",
    version="1.1.0"
)

# In-memory session state
molab_state = {
    "status": "ONLINE",
    "active_notebook_url": None,
    "active_notebook_name": None,
    "gpu": "NVIDIA RTX Pro 6000 (Blackwell)",
    "terminal_ready": True,
    "last_command": None,
    "last_updated": time.time()
}

class ExecRequest(BaseModel):
    command: str
    delay_ms: int = 10
    wait_sec: float = 2.0

class DeployRequest(BaseModel):
    gpu_type: str = "RTX Pro 6000 (Blackwell)"
    bootstrap_supercluster: bool = True

class MolabDriver:
    @staticmethod
    async def get_browser():
        p = await async_playwright().start()
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            return p, browser
        except Exception as e:
            await p.stop()
            raise RuntimeError(f"Cannot connect to Chromium CDP on {CDP_URL}: {e}")

    @staticmethod
    async def get_active_session_frame(page):
        # Look for iframe with sb.molab.run
        iframes = await page.query_selector_all("iframe")
        for ifr in iframes:
            src = await ifr.get_attribute("src")
            if src and "sb.molab.run" in src:
                frame = await ifr.content_frame()
                if frame:
                    return frame
        # Fallback to page.frames
        for f in page.frames:
            if "sb.molab.run" in f.url:
                return f
        return page.main_frame

    @staticmethod
    async def read_terminal_buffer(frame, max_lines: int = 50):
        try:
            lines = await frame.evaluate(r"""() => {
                let el = document.querySelector(".xterm");
                while (el) {
                    const k = Object.keys(el).find(k => k.startsWith("__reactFiber"));
                    if (k) {
                        let fiber = el[k];
                        let depth = 0;
                        while (fiber && depth < 25) {
                            if (fiber.memoizedState) {
                                let s = fiber.memoizedState;
                                while (s) {
                                    if (s.memoizedState && typeof s.memoizedState === "object") {
                                        for (let key of ["terminal", "term"]) {
                                            let t = s.memoizedState[key];
                                            if (t && t.buffer) {
                                                const buf = t.buffer.active;
                                                const res = [];
                                                for (let i = 0; i < buf.length; i++) {
                                                    const l = buf.getLine(i);
                                                    if (l) res.push(l.translateToString(true));
                                                }
                                                return res.filter(x => x.trim().length > 0);
                                            }
                                        }
                                    }
                                    s = s.next;
                                }
                            }
                            fiber = fiber.return;
                            depth++;
                        }
                    }
                    el = el.parentElement;
                }
                return [];
            }""")
            return lines[-max_lines:] if lines else []
        except Exception as e:
            logger.warning(f"Error reading terminal buffer: {e}")
            return []

    @staticmethod
    async def create_vm(gpu_type: str = "RTX Pro 6000 (Blackwell)"):
        p, browser = await MolabDriver.get_browser()
        try:
            context = browser.contexts[0]
            try:
                await context.grant_permissions(['clipboard-read', 'clipboard-write'])
            except Exception:
                pass
            page = context.pages[0] if context.pages else await context.new_page()

            logger.info("Step 1: Navigating to https://molab.marimo.io/notebooks ...")
            await page.goto("https://molab.marimo.io/notebooks", wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)

            logger.info("Step 2: Clicking 'Create a notebook' ...")
            create_btn = await page.wait_for_selector('text="Create a notebook"', timeout=10000)
            await create_btn.click()
            await page.wait_for_timeout(3500)

            notebook_url = page.url
            notebook_name = (await page.title()).replace(" - molab", "").strip()
            logger.info(f"Notebook created: {notebook_name} ({notebook_url})")

            # Configure Compute to GPU
            if "RTX" in gpu_type or "Blackwell" in gpu_type:
                logger.info(f"Step 3: Configuring Compute to {gpu_type} ...")
                compute_btn = await page.wait_for_selector('button:has-text("Compute")', timeout=8000)
                await compute_btn.click()
                await page.wait_for_timeout(1000)

                # Click GPU select
                gpu_trigger = await page.wait_for_selector('text="None"', timeout=5000)
                await gpu_trigger.click()
                await page.wait_for_timeout(800)

                # Select Blackwell
                opt = await page.wait_for_selector('text="RTX Pro 6000 (Blackwell)"', timeout=5000)
                await opt.click()
                await page.wait_for_timeout(500)

                # Apply and restart
                apply_btn = await page.wait_for_selector('button:has-text("Apply and restart")', timeout=5000)
                await apply_btn.click()
                logger.info("Applied RTX 6000 Blackwell compute tier. Waiting for provisioning...")
                await page.wait_for_timeout(8000)

            # Wait for session iframe
            logger.info("Step 4: Locating session sandbox iframe...")
            session_frame = None
            for _ in range(20):
                session_frame = await MolabDriver.get_active_session_frame(page)
                if session_frame and session_frame != page.main_frame:
                    break
                await page.wait_for_timeout(1000)

            if not session_frame:
                raise RuntimeError("Could not find session sandbox iframe on Molab page.")

            # Check if terminal already exists
            term_exists = await session_frame.query_selector('.xterm')
            terminal_clicked = bool(term_exists)

            if not terminal_clicked:
                logger.info("Step 5: Injecting '!sudo apt install fastfetch' cell to trigger terminal button...")
                editor = await session_frame.wait_for_selector('.cm-content', timeout=25000)
                await editor.click()
                await page.wait_for_timeout(300)

                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await page.keyboard.type("!sudo apt install fastfetch", delay=10)
                await page.wait_for_timeout(400)

                logger.info("Step 6: Executing cell with Control+Enter...")
                await page.keyboard.press("Control+Enter")
                await page.wait_for_timeout(3500)

                logger.info("Step 7: Locating and clicking 'Open terminal' button...")
                for _ in range(12):
                    buttons = await session_frame.query_selector_all('button, [role="button"]')
                    for b in buttons:
                        txt = (await b.inner_text()).strip()
                        if "open terminal" in txt.lower():
                            await b.click()
                            terminal_clicked = True
                            logger.info("Successfully clicked 'Open terminal' button!")
                            break
                    if terminal_clicked:
                        break
                    await page.wait_for_timeout(1000)

                if not terminal_clicked:
                    # Fallback: click Terminal button in marimo header
                    for b in await session_frame.query_selector_all('button, [role="button"]'):
                        txt = (await b.inner_text()).strip()
                        if txt == "Terminal":
                            await b.click()
                            terminal_clicked = True
                            break

            await page.wait_for_timeout(2000)

            molab_state["status"] = "ACTIVE"
            molab_state["active_notebook_url"] = notebook_url
            molab_state["active_notebook_name"] = notebook_name
            molab_state["terminal_ready"] = terminal_clicked
            molab_state["last_updated"] = time.time()

            return {
                "success": True,
                "notebook_url": notebook_url,
                "notebook_name": notebook_name,
                "gpu": gpu_type,
                "terminal_ready": terminal_clicked
            }
        finally:
            await p.stop()

    @staticmethod
    async def exec_in_terminal(command: str, delay_ms: int = 10, wait_sec: float = 2.0):
        p, browser = await MolabDriver.get_browser()
        try:
            context = browser.contexts[0]
            try:
                await context.grant_permissions(['clipboard-read', 'clipboard-write'])
            except Exception:
                pass
            page = context.pages[0] if context.pages else None
            if not page:
                raise RuntimeError("No active page found in browser.")

            session_frame = await MolabDriver.get_active_session_frame(page)
            logger.info(f"Dispatching terminal command: {command[:60]}...")

            # Type directly into xterm helper textarea for 100% reliable focus
            helper = await session_frame.query_selector('.xterm-helper-textarea')
            if helper:
                await helper.focus()
                await helper.type(f"{command}\n", delay=delay_ms)
            else:
                # Fallback: click terminal area and use keyboard
                term_area = await session_frame.query_selector('.xterm, .terminal')
                if term_area:
                    await term_area.click()
                else:
                    await page.mouse.click(500, 550)
                await page.wait_for_timeout(200)
                await page.keyboard.type(f"{command}\n", delay=delay_ms)

            await page.wait_for_timeout(int(wait_sec * 1000))

            # Read back updated buffer
            lines = await MolabDriver.read_terminal_buffer(session_frame, max_lines=40)
            output_text = "\n".join(lines)

            molab_state["last_command"] = command
            molab_state["last_updated"] = time.time()

            return {
                "success": True,
                "command": command,
                "output": output_text,
                "lines": lines
            }
        finally:
            await p.stop()

    @staticmethod
    async def get_terminal_output(max_lines: int = 50):
        p, browser = await MolabDriver.get_browser()
        try:
            page = browser.contexts[0].pages[0] if browser.contexts[0].pages else None
            if not page:
                return []
            session_frame = await MolabDriver.get_active_session_frame(page)
            return await MolabDriver.read_terminal_buffer(session_frame, max_lines=max_lines)
        finally:
            await p.stop()

@app.get("/health")
def health():
    return {
        "service": "TrueEngine Molab Marimo Autonomous VM API",
        "status": "online",
        "cdp_port": 9222,
        "time": time.time()
    }

@app.get("/status")
def status():
    return molab_state

@app.get("/api/terminal")
async def get_terminal(lines: int = Query(default=40, ge=1, le=200)):
    try:
        output_lines = await MolabDriver.get_terminal_output(max_lines=lines)
        return {
            "success": True,
            "line_count": len(output_lines),
            "lines": output_lines,
            "output": "\n".join(output_lines)
        }
    except Exception as e:
        logger.error(f"Error fetching terminal buffer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create_vm")
async def create_vm(req: DeployRequest):
    try:
        res = await MolabDriver.create_vm(gpu_type=req.gpu_type)
        if req.bootstrap_supercluster:
            bootstrap_cmd = (
                f"cd /marimo && "
                f"rm -rf TrueEngine-V1 && "
                f"git clone https://github.com/RealTrueHieu/TrueEngine-V1.git && "
                f"cd TrueEngine-V1 && "
                f"echo 'HF_TOKEN={HF_TOKEN}' > .env && "
                f"pip install -q huggingface_hub onnx onnxscript tqdm requests chess && "
                f"nohup python3 -u molab_supercluster_node.py > molab_node.log 2>&1 &"
            )
            await asyncio.sleep(2)
            exec_res = await MolabDriver.exec_in_terminal(bootstrap_cmd, wait_sec=4.0)
            res["supercluster_deployed"] = True
            res["bootstrap_output"] = exec_res.get("output", "")
        return res
    except Exception as e:
        logger.error(f"Error creating VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/exec")
async def execute_command(req: ExecRequest):
    try:
        res = await MolabDriver.exec_in_terminal(req.command, delay_ms=req.delay_ms, wait_sec=req.wait_sec)
        return res
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/redeploy")
async def redeploy_supercluster():
    try:
        redeploy_cmd = (
            f"cd /marimo/TrueEngine-V1 && "
            f"git checkout -- . && "
            f"git pull && "
            f"pkill -f molab_supercluster_node || true && "
            f"echo 'HF_TOKEN={HF_TOKEN}' > .env && "
            f"nohup python3 -u molab_supercluster_node.py > molab_node.log 2>&1 &"
        )
        res = await MolabDriver.exec_in_terminal(redeploy_cmd, wait_sec=3.0)
        return {
            "success": True,
            "message": "TrueEngine Blackwell Supercluster redeployed successfully",
            "output": res.get("output", "")
        }
    except Exception as e:
        logger.error(f"Error redeploying supercluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
