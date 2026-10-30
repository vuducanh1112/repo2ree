import { expect, type Locator, type Page, test } from "@playwright/test";

/**
 * Narration for a showcase scenario recorded as the demo: a focus box, a pulse
 * ring and a caption drawn over the part of the page a step is about, held long
 * enough to read. It draws only in a project that says `metadata.narrated`
 * (the demo-gui project); everywhere else {@link narrate} returns at once, so
 * the scenario a demo records is exactly the one the showcase tier judges.
 */

const NARRATION_DWELL_MS = 1500;

function narrated(): boolean {
  return test.info().project.metadata?.narrated === true;
}

/** Caption the target and dwell on it, in a narrated run; nothing otherwise. */
export async function narrate(page: Page, target: Locator, caption: string): Promise<void> {
  if (!narrated()) return;
  const element = target.first();
  await expect(element).toBeVisible({ timeout: 10000 });
  await element.scrollIntoViewIfNeeded();
  await showFocus(element, caption);
  await page.waitForTimeout(NARRATION_DWELL_MS);
}

/** Draw the focus box, pulse ring, and optional narration label on a target. */
async function showFocus(locator: Locator, narration?: string) {
  await locator.evaluate((el, text) => {
    const containerId = "__ree_demo_focus_container__";
    const boxId = "__ree_demo_focus_box__";
    const pulseId = "__ree_demo_focus_pulse__";
    const labelId = "__ree_demo_focus_label__";

    let container = document.getElementById(containerId);
    if (!container) {
      container = document.createElement("div");
      container.id = containerId;
      Object.assign(container.style, {
        position: "fixed",
        left: "0",
        top: "0",
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: "2147483647",
      });
      document.body.appendChild(container);

      const style = document.createElement("style");
      style.id = "__ree_demo_focus_style__";
      style.textContent = `
				@keyframes reeDemoPulse {
					0% { transform: scale(1); opacity: 0.55; }
					70% { transform: scale(1.08); opacity: 0.18; }
					100% { transform: scale(1.16); opacity: 0; }
				}
			`;
      document.head.appendChild(style);
    }

    let pulse = document.getElementById(pulseId);
    if (!pulse) {
      pulse = document.createElement("div");
      pulse.id = pulseId;
      Object.assign(pulse.style, {
        position: "fixed",
        border: "2px solid rgba(255, 199, 0, 0.95)",
        borderRadius: "10px",
        boxSizing: "border-box",
        pointerEvents: "none",
        animation: "reeDemoPulse 1.1s ease-out infinite",
      });
      container.appendChild(pulse);
    }

    let box = document.getElementById(boxId);
    if (!box) {
      box = document.createElement("div");
      box.id = boxId;
      Object.assign(box.style, {
        position: "fixed",
        border: "2px solid #ffc700",
        borderRadius: "10px",
        boxShadow: "0 0 0 3px rgba(255, 199, 0, 0.18)",
        boxSizing: "border-box",
        pointerEvents: "none",
      });
      container.appendChild(box);
    }

    let label = document.getElementById(labelId);
    if (!label) {
      label = document.createElement("div");
      label.id = labelId;
      Object.assign(label.style, {
        position: "fixed",
        background: "rgba(0, 0, 0, 0.88)",
        color: "#fff",
        padding: "6px 9px",
        borderRadius: "7px",
        font: "600 12px/1.35 ui-sans-serif, system-ui, sans-serif",
        boxShadow: "0 6px 20px rgba(0,0,0,0.32)",
        pointerEvents: "none",
        maxWidth: "360px",
        whiteSpace: "normal",
      });
      container.appendChild(label);
    }

    const rect = el.getBoundingClientRect();
    const pad = 6;
    const left = Math.max(6, rect.left - pad);
    const top = Math.max(6, rect.top - pad);
    const width = Math.max(24, rect.width + pad * 2);
    const height = Math.max(24, rect.height + pad * 2);

    for (const element of [pulse, box]) {
      element.style.left = `${left}px`;
      element.style.top = `${top}px`;
      element.style.width = `${width}px`;
      element.style.height = `${height}px`;
      element.style.display = "block";
    }

    if (text) {
      label.textContent = text;
      label.style.display = "block";
      label.style.left = `${left}px`;
      label.style.top = `${Math.max(6, top - 36)}px`;
    } else {
      label.style.display = "none";
    }
  }, narration);
}
