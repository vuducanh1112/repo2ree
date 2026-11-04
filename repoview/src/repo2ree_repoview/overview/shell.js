// The overview's frame for its bundled evidence: the page after "#", beside the sidebar.
// Only a page the overview bundled under evidence/ is shown; its own address after a second "#" reaches it.
(() => {
  const frame = document.getElementById("shown");
  const missing = document.getElementById("missing");
  const from = new URLSearchParams(location.search).get("from");
  document.querySelectorAll("nav a").forEach((link) => {
    link.classList.toggle("current", from !== null && link.getAttribute("href") === `${from}.html`);
  });
  const show = () => {
    const target = decodeURIComponent(location.hash.slice(1));
    const path = target.split("#")[0];
    const bundled = /^evidence\/[A-Za-z0-9._\/-]+\.html$/.test(path) && !path.split("/").includes("..");
    frame.hidden = !bundled;
    missing.hidden = bundled;
    if (bundled && frame.getAttribute("src") !== target) frame.setAttribute("src", target);
  };
  window.addEventListener("hashchange", show);
  show();
})();
