document.documentElement.classList.add('js');
(function(){
  const root=document.documentElement;
  try{const saved=localStorage.getItem('research-theme');if(saved==='dark'||saved==='light')root.dataset.theme=saved;}catch(e){}
  const toggle=document.querySelector('[data-theme-toggle]');
  function label(){if(toggle){const dark=root.dataset.theme==='dark';toggle.setAttribute('aria-label',dark?'Switch to light theme':'Switch to dark theme');toggle.setAttribute('aria-pressed',String(dark));toggle.textContent=dark?'☀':'◐';}}
  label();
  if(toggle)toggle.addEventListener('click',()=>{const theme=root.dataset.theme==='dark'?'light':'dark';root.dataset.theme=theme;try{localStorage.setItem('research-theme',theme);}catch(e){}label();});
  const search=document.getElementById('concept-search'),count=document.getElementById('concept-count');
  const concepts=Array.from(document.querySelectorAll('[data-concept]'));
  if(search&&count){search.addEventListener('input',()=>{const term=search.value.trim().toLowerCase();let visible=0;concepts.forEach(item=>{const match=item.textContent.toLowerCase().includes(term);item.hidden=!match;if(match)visible++;});count.textContent=visible+' of '+concepts.length+' concepts'+(visible===0?' — try another term.':'.');});}
})();