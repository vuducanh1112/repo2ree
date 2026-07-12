import { expect, type Locator, type Page, test } from "@playwright/test";
import { stepShot } from "../../screenshot";

/**
 * Shared toolkit for the narrated demo specs (recorded walkthroughs). Each
 * helper acts like its e2e counterpart in helpers/flow.ts but adds the demo
 * chrome: a focus box + pulse ring around the target, an optional narration
 * label, and pacing delays so the recording is watchable.
 *
 * Pacing differs per demo (a long pipeline walkthrough breathes slower than a
 * quick upload demo), so the kit is a factory: create it once per spec with
 * the delays that fit, then use the returned helpers everywhere.
 */
interface DemoKitOptions {
  /** Pause around each action (before focus, after click/fill). */
  stepDelayMs?: number;
  /** Extra dwell when a narration label is shown. */
  narrationDelayMs?: number;
}

export function createDemoKit(options: DemoKitOptions = {}) {
  const stepDelayMs = options.stepDelayMs ?? 350;
  const narrationDelayMs = options.narrationDelayMs ?? 900;

  /**
   * A demo step: runs the body inside a named `test.step` (so the trace/report
   * groups its actions) and captures a named, ordered screenshot before and
   * after the step's UI has settled.
   */
  async function demoStep(page: Page, name: string, body: () => Promise<void>) {
    await stepShot(page, name, "before");
    await test.step(name, body);
    await stepShot(page, name, "after");
  }

  /** Draw the focus box, pulse ring, and optional narration label on a target. */
  async function showDemoFocus(locator: Locator, narration?: string) {
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

  /** Focus the target, dwell, then perform an action on it. */
  async function focusThen(
    page: Page,
    locator: Locator,
    narration: string | undefined,
    action: (target: Locator) => Promise<void>,
  ) {
    const target = locator.first();
    await expect(target).toBeVisible({ timeout: 10000 });
    await target.scrollIntoViewIfNeeded();
    await showDemoFocus(target, narration);
    if (narration) {
      await page.waitForTimeout(narrationDelayMs);
    }
    await page.waitForTimeout(stepDelayMs);
    await action(target);
    await page.waitForTimeout(stepDelayMs);
  }

  async function clickDemo(page: Page, locator: Locator, narration?: string) {
    await focusThen(page, locator, narration, (target) => target.click());
  }

  async function fillDemo(page: Page, locator: Locator, value: string, narration?: string) {
    await focusThen(page, locator, narration, (target) => target.fill(value));
  }

  async function selectDemo(page: Page, locator: Locator, value: string, narration?: string) {
    await focusThen(page, locator, narration, async (target) => {
      await target.selectOption(value);
    });
  }

  /** Resolve a runnable-script textbox given either its locator or its ARIA name. */
  function scriptEditor(page: Page, editor: Locator | string): Locator {
    return typeof editor === "string"
      ? page.getByRole("main").getByRole("textbox", { name: editor, exact: true })
      : editor;
  }

  // Author a runnable's run script: fill the RunScriptCard textarea, then click
  // its "Save run script" button (shared by activation and experiment editors).
  async function saveRunScript(
    page: Page,
    editor: Locator | string,
    content: string,
    narration?: string,
  ) {
    await fillDemo(page, scriptEditor(page, editor), content, narration);
    await clickDemo(
      page,
      page.getByRole("main").getByRole("button", { name: "Save run script", exact: true }).first(),
    );
  }

  /** Author and declare a runnable's verify script. */
  async function saveVerifyScript(
    page: Page,
    editor: Locator | string,
    content: string,
    narration?: string,
  ) {
    await fillDemo(page, scriptEditor(page, editor), content, narration);
    await clickDemo(
      page,
      page
        .getByRole("main")
        .getByRole("button", { name: "Save verify script", exact: true })
        .first(),
    );
  }

  /** Scroll the page by a wheel tick and dwell, so the recording can pan. */
  async function showcaseScroll(page: Page, deltaY = 700) {
    await page.mouse.wheel(0, deltaY);
    await page.waitForTimeout(700);
  }

  /** Dwell on a panel with a narration label, without interacting with it. */
  async function showcasePanel(page: Page, locator: Locator, narration: string) {
    await expect(locator).toBeVisible({ timeout: 10000 });
    await locator.scrollIntoViewIfNeeded();
    await showDemoFocus(locator, narration);
    await page.waitForTimeout(1200);
  }

  return {
    demoStep,
    showDemoFocus,
    clickDemo,
    fillDemo,
    selectDemo,
    saveRunScript,
    saveVerifyScript,
    showcaseScroll,
    showcasePanel,
  };
}
