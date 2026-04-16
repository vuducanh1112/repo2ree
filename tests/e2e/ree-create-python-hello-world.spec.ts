import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "../../frontend/node_modules/@playwright/test";

test("upload source archive into workspace", async ({ page }) => {
	test.setTimeout(180000);

	const expectOverviewCableActive = async (label: string) => {
		await expect(page.getByText(`✓ ${label}`, { exact: true })).toBeVisible();
	};

	const sourceArchive = path.resolve(__dirname, "resources/examples/python-hello-world.tar.gz");
	const archiveEntries = execFileSync("tar", ["-tzf", sourceArchive], { encoding: "utf8" })
		.split("\n")
		.map((entry) => entry.trim())
		.filter(Boolean);
	const archiveNodeNames = [...
		new Set(
			archiveEntries
				.map((entry) => entry.replace(/\/+$/, "").split("/").filter(Boolean).pop())
				.filter((name): name is string => Boolean(name)),
		),
	];
	const step3WorkspaceActions = page
		.locator("div")
		.filter({ hasText: "Step 3: Workspace Actions" })
		.filter({ hasText: "1/1" })
		.first();
	const main = page.getByRole("main");

	await page.goto("/");
	await page.getByRole("button", { name: "Create REE" }).click();

	await expect(page.getByRole('main').getByText('Source Repo', { exact: true })).toBeVisible();
	await page.getByRole("button", { name: "Upload tarball" }).click();

	await page
		.locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
		.setInputFiles(sourceArchive);
	await page.getByRole("button", { name: /Add to workspace/i }).click();

	await expect(step3WorkspaceActions).toBeVisible();
	await expect(
		step3WorkspaceActions.getByRole("button", { name: /Clear workspace source/i }),
	).toBeVisible();
	await expect(
		step3WorkspaceActions.getByRole("button", { name: /Browse workspace files/i }),
	).toBeVisible();
	await expect(page.getByText("Source configuration is locked.")).toBeVisible();
	await expect(page.getByText("python-hello-world.tar.gz", { exact: true })).toBeVisible();

	await step3WorkspaceActions.getByRole("button", { name: /Browse workspace files/i }).click();

	await expect(main.getByText("Files", { exact: true })).toBeVisible();
	await expect(page.getByText("Workspace", { exact: true })).toBeVisible();
	for (const nodeName of archiveNodeNames) {
		const escapedNodeName = nodeName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
		await expect(page.getByRole("button", { name: new RegExp(escapedNodeName) })).toBeVisible();
	}

	await page
		.getByRole("button", { name: /Provide Metadata.*Input metadata about the project/ })
		.click();
	await expect(main.getByText("Provide Metadata", { exact: true })).toBeVisible();
	await page.getByPlaceholder("my-project-v1.0").fill("ree-hello-world");
	await expect(page.getByPlaceholder("my-project-v1.0")).toHaveValue("ree-hello-world");

	await page.getByRole("button", { name: /Evaluate.*Score reproducibility level/ }).click();
	await expect(main.getByText("Evaluate", { exact: true })).toBeVisible();
	await main.getByRole("button", { name: /^Play Run$/ }).click();
	await expect(main.getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 20000 });
	await expectOverviewCableActive("Evaluate");

	await page.getByRole("button", { name: /Build Runtime.*Build the runtime tarball/ }).click();
	await expect(main.getByText("Build Runtime", { exact: true })).toBeVisible();
	await page.getByPlaceholder("build_runtime.sh").fill("python_hello_world/build_runtime.sh");
	await page.getByPlaceholder("runtime.tar.gz").fill("python_hello_world/runtime.tar");
	await main.getByRole("button", { name: /Run build/ }).click();
	await expect(main.getByRole("button", { name: /Re-build/ })).toBeVisible({ timeout: 20000 });
	await expectOverviewCableActive("Runtime");
	const buildOutputVerification = main
		.locator("div")
		.filter({ hasText: "Step 3: Verify Build Output" })
		.filter({ hasText: "python_hello_world/runtime.tar" })
		.filter({ hasText: "✓ produced by build" })
		.first();
	await expect(buildOutputVerification).toBeVisible({ timeout: 20000 });

	await page.getByRole("button", { name: /Generate SBOM.*Scan runtime with syft/ }).click();
	await expect(main.getByText("Generate SBOM", { exact: true })).toBeVisible();
	await main.getByRole("button", { name: /^Play Generate SBOM$/ }).click();
	await expect(main.getByRole("button", { name: /Regenerate SBOM/ })).toBeVisible({ timeout: 20000 });
	await expect(main.getByText("SBOM run succeeded", { exact: true })).toBeVisible({ timeout: 20000 });
	await expectOverviewCableActive("SBOM");

	await page.getByRole("button", { name: /Test Activation.*Verify container activates/ }).click();
	await expect(main.getByText("Test Activation", { exact: true })).toBeVisible();
	await page.getByPlaceholder("activation_test.sh").fill("python_hello_world/activate_runtime.sh");
	await main.getByRole("button", { name: /Run activation/ }).click();
	await expect(main.getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 20000 });
	//await expect(main.getByText("Activation run succeeded", { exact: true })).toBeVisible({ timeout: 20000 });
	await expectOverviewCableActive("Activation");
});
