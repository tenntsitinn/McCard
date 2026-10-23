'use strict';
window.mcpCredentials=(()=>{
 let pending=null;
 const dialog=document.createElement('dialog');dialog.className='mcp-dialog';
 dialog.innerHTML='<form><h2>接入你的麦当劳账号</h2><p>使用你自己的 MCP API Key 查询最近订单、菜单和使用卡牌。</p><a href="https://open.mcd.cn/mcp" target="_blank" rel="noopener noreferrer">前往麦当劳官方申请 MCP API Key ↗</a><label>个人 MCP API Key<input type="password" required maxlength="8192" autocomplete="off" spellcheck="false"></label><p class="mcp-note">密钥仅保存在服务器会话内，8小时后失效；不会保存到浏览器或项目文件。</p><p role="status" class="mcp-error"></p><div><button type="button" class="mcp-cancel">取消</button><button type="submit">接入并继续</button></div></form>';
 document.body.append(dialog);
 const input=dialog.querySelector('input'),status=dialog.querySelector('[role=status]'),form=dialog.querySelector('form');
 async function update(body){const b=await (await fetch('/api/bootstrap')).json();const r=await fetch('/api/mcp-session',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':b.csrf},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'接入失败');return data;}
 function prompt(){if(pending)return pending;pending=new Promise((resolve,reject)=>{
 const close=()=>{input.value='';pending=null;reject(Error('请先接入自己的 MCP API Key。'));};
 dialog.addEventListener('close',close,{once:true});status.textContent='';dialog.showModal();
 form.onsubmit=async e=>{e.preventDefault();const token=input.value.trim();if(!token){status.textContent='请填写个人 MCP API Key。';return;}const submit=form.querySelector('[type=submit]');submit.disabled=true;
 try{await update({token});input.value='';dialog.removeEventListener('close',close);dialog.close();pending=null;resolve();}catch(error){status.textContent=error.message;}finally{submit.disabled=false;}};
 });return pending;}
 dialog.querySelector('.mcp-cancel').onclick=()=>dialog.close();
 return {async ensure(){const r=await fetch('/api/mcp-session');if(!r.ok)throw Error('无法检查 MCP 接入状态');if(!(await r.json()).connected)await prompt();}};
})();
