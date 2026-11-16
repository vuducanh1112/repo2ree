document.querySelectorAll('input.filter').forEach(input=>{
  const target=document.getElementById(input.dataset.target);
  input.addEventListener('input',()=>{const q=input.value.toLowerCase();
    target.querySelectorAll('[data-row]').forEach(row=>{row.style.display=row.textContent.toLowerCase().includes(q)?'':'none'})})});
// A link to a drawing collapsed under its <details> opens it there.
function openLinked(){const id=decodeURIComponent(location.hash.slice(1));const target=id&&document.getElementById(id);
  if(target&&target.tagName==='DETAILS'){target.open=true;target.scrollIntoView();}}
window.addEventListener('hashchange',openLinked);openLinked();
