document.querySelectorAll('input.filter').forEach(input=>{
  const target=document.getElementById(input.dataset.target);
  input.addEventListener('input',()=>{const q=input.value.toLowerCase();
    target.querySelectorAll('[data-row]').forEach(row=>{row.style.display=row.textContent.toLowerCase().includes(q)?'':'none'})})});
