'use strict';
const $ = id => document.getElementById(id);
const MAX_CARDS=16;
const state = {csrf:'', presets:[], tagFilter:'全部', context:null, restaurant:null, menu:null, category:'全部', draft:[], detail:null, editing:-1, editingCard:null, checks:[], epoch:0, libraryIndex:0, selectedCard:null, checkoutCard:null, checkoutQuote:null, wheelReadyAt:0};
const libraryPage=location.pathname==='/library';
const LIBRARY_STORE_KEY='mccard.libraryRestaurant';
let openLibraryAfterStore=false;
document.body.classList.toggle('is-library',libraryPage);
if(libraryPage){$('headerActionLabel').textContent='+创建卡牌';$('count').hidden=true;}
function el(tag, text, cls) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n; }
function button(text, action, cls) {const n=el('button',text,cls);n.type='button';n.onclick=action;return n;}
function tell(text){$('notice').textContent=text;}
function rememberedRestaurant(){try{const value=JSON.parse(sessionStorage.getItem(LIBRARY_STORE_KEY));if(!value||typeof value.storeCode!=='string'||![1,5].includes(value.beType)||typeof value.storeName!=='string'||typeof value.address!=='string'||(value.beType===5&&typeof value.beCode!=='string'))return null;return value;}catch{return null;}}
function applyRestaurant(value){state.restaurant=value;state.context={storeCode:value.storeCode,beType:value.beType};if(value.beType===5)state.context.beCode=value.beCode;}
function rememberRestaurant(value){try{sessionStorage.setItem(LIBRARY_STORE_KEY,JSON.stringify(value));}catch{}applyRestaurant(value);}
async function api(route, body){if(body&&!['/api/cards-save','/api/delete','/api/save'].includes(route))await window.mcpCredentials.ensure();const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),180000);try{const r=await fetch(route,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':state.csrf}:{},body:body?JSON.stringify(body):undefined,signal:controller.signal});const data=await r.json();if(!r.ok)throw Error(data.error||'请求未完成，请重试。');return data;}catch(e){if(e.name==='AbortError')throw Error('查询超时，请重试。');throw e;}finally{clearTimeout(timeout);}}
async function busy(btn, work, target=tell){const old=btn.textContent;btn.disabled=true;btn.textContent='正在处理…';try{await work();}catch(e){target(e.message);}finally{btn.disabled=false;btn.textContent=old;}}
function showDialog(id){$(id).showModal();}
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
const cities=['惠州','广州','深圳','东莞','佛山','珠海','中山','北京','上海','天津','重庆','杭州','南京','苏州','成都','武汉','西安','长沙','郑州','厦门','福州','济南','青岛','沈阳','大连','昆明','南宁','海口'];
for(const city of cities){const option=el('option',city);option.value=city;$('city').append(option);}
const otherOption=el('option','其他城市…');otherOption.value='other';$('city').append(otherOption);
let storeRequest=0, storeResults=[], resultMode=null;
function clearStores(message){storeResults=[];resultMode=null;$('storeSelect').replaceChildren(el('option',message));$('storeSelect').disabled=true;$('confirmStore').disabled=true;$('storeAddress').textContent='';}
async function queryStores(){
 const request=++storeRequest;clearStores('正在查询…');
 const city=$('city').value==='other'?$('otherCity').value.trim():$('city').value;
 if(!city){clearStores('请填写城市后查询');$('storeMessage').textContent='常用城市列表未覆盖全部城市，可在此填写其他城市。';return;}
 const mode=Number(document.querySelector('input[name=mode]:checked').value);
 $('storeMessage').textContent='正在查询门店…';
 try{const data=await api('/api/stores',{city,keyword:$('keyword').value.trim()||'麦当劳',beType:mode});
 if(request!==storeRequest)return;
 storeResults=data.stores;resultMode=mode;
 const select=$('storeSelect');select.replaceChildren();const placeholder=el('option',data.stores.length?'请选择一家门店':'未找到门店');placeholder.value='';select.append(placeholder);
 data.stores.forEach((store,index)=>{const available=store.businessStatus===true&&(mode!==5||store.beCode);const option=el('option',`${store.storeName}${available?'':'（当前不可选）'}`);option.value=String(index);option.disabled=!available;select.append(option);});
 select.disabled=!data.stores.length;
 $('storeMessage').textContent=data.stores.length?`查询到 ${data.stores.length} 家门店，请从下方选择。结果由位置搜索返回，不代表全市全部门店。`:'未找到门店。可以补充商圈或街道，再查询一次。';
 }catch(e){if(request!==storeRequest)return;clearStores('查询失败，请重试');$('storeMessage').textContent=e.message;}
}
function requestRestaurant(thenOpenLibrary=false){openLibraryAfterStore=thenOpenLibrary;showDialog('storeDialog');queryStores();}
$('storeForm').onsubmit=event=>{event.preventDefault();queryStores();};
$('city').onchange=()=>{$('otherCityLabel').hidden=$('city').value!=='other';$('keyword').value='';queryStores();};
document.querySelectorAll('input[name=mode]').forEach(input=>input.onchange=queryStores);
$('keyword').oninput=()=>{storeRequest++;clearStores('筛选条件已变更，请点击查询');$('storeMessage').textContent='点击“查询 / 刷新门店”获取新的结果。';};
$('otherCity').oninput=()=>{storeRequest++;clearStores('城市已变更，请点击查询');};
$('storeSelect').onchange=()=>{const value=$('storeSelect').value;const store=value===''?null:storeResults[Number(value)];$('confirmStore').disabled=!store||store.businessStatus!==true||(resultMode===5&&!store.beCode);$('storeAddress').textContent=store?`${store.address} · ${store.businessStatus===true?'营业中':'暂不可选'}`:'';};
async function checkLibrary(){
 const request=++state.epoch;state.checks=[];renderLibrary();$('libraryMessage').textContent='正在按当前餐厅检查卡包…';
 try{const result=await api('/api/library-check',{context:state.context});if(request!==state.epoch)return;state.checks=result.cards;renderLibrary();$('libraryMessage').textContent='';}
 catch(e){if(request===state.epoch)$('libraryMessage').textContent=e.message;}
}
function money(cents){return typeOfNumber(cents)?`¥${(cents/100).toFixed(2)}`:'—';}
function typeOfNumber(value){return typeof value==='number'&&Number.isFinite(value);}
function renderCheckout(quote){
 const root=$('checkoutSummary');root.replaceChildren();
 const total=el('div',undefined,'checkout-total');total.append(el('span','本次应付'),el('strong',money(quote.price)));root.append(total);
 const lines=el('div',undefined,'checkout-lines');
 for(const [label,key] of [['餐品','productPrice'],['打包费','packingPrice'],['餐具费','tablewarePrice'],['优惠','discount']]){
  if(!typeOfNumber(quote[key])||quote[key]===0)continue;
  const row=el('p');row.append(el('span',label),el('span',`${key==='discount'?'- ':''}${money(quote[key])}`));lines.append(row);
 }
 if(lines.children.length)root.append(lines);
}
async function refreshCheckout(){
 const card=state.checkoutCard;if(!card)return;
 state.checkoutQuote=null;$('createOrder').disabled=true;$('takeWay').disabled=true;$('checkoutMessage').textContent='正在按当前门店核价…';
 try{
  const data=await api('/api/checkout-price',{id:card.id,context:state.context,needTableware:$('needTableware').checked});
  state.checkoutQuote=data;renderCheckout(data.quote);
  const select=$('takeWay');select.replaceChildren();
  for(const option of data.takeWayList){const node=el('option',`${option.title||'取餐'}${option.subtitle?` · ${option.subtitle}`:''}`);node.value=option.code;select.append(node);}
  select.disabled=!data.takeWayList.length;$('createOrder').disabled=!data.takeWayList.length;
  $('checkoutMessage').textContent=data.takeWayList.length?'价格已更新，请确认取餐方式。':'当前核价结果没有可用取餐方式。';
 }catch(e){$('checkoutSummary').replaceChildren(el('p','暂时无法核价，请稍后重试。'));$('checkoutMessage').textContent=e.message;}
}
async function openCheckout(card){
 state.checkoutCard=card;state.checkoutQuote=null;$('checkoutTitle').textContent=card.name;$('needTableware').checked=false;
 $('takeWay').replaceChildren(el('option','正在核价…'));$('takeWay').disabled=true;$('createOrder').disabled=true;
 showDialog('checkoutDialog');await refreshCheckout();
}
$('needTableware').onchange=refreshCheckout;
$('createOrder').onclick=()=>busy($('createOrder'),async()=>{
 const priced=state.checkoutQuote;if(!priced||!state.checkoutCard)throw Error('请先完成核价。');
 const result=await api('/api/checkout-create',{id:state.checkoutCard.id,context:state.context,needTableware:$('needTableware').checked,takeWayCode:$('takeWay').value,expectedPrice:priced.quote.price});
 if(result.payH5Url){const target=new URL(result.payH5Url);if(target.protocol!=='https:')throw Error('支付链接格式异常，请到麦当劳官方渠道查看订单。');location.assign(target.href);return;}
 $('checkoutMessage').textContent=`订单 ${result.orderId||''} 已创建，请到麦当劳官方渠道完成支付。`;
},message=>$('checkoutMessage').textContent=message);
$('confirmStore').onclick=()=>busy($('confirmStore'),async()=>{
 const value=$('storeSelect').value;const store=value===''?null:storeResults[Number(value)];if(!store||store.businessStatus!==true)throw Error('请先选择营业中的门店。');
 const mode=resultMode;const selection={storeCode:store.storeCode,storeName:store.storeName,address:store.address,beType:mode};if(mode===5)selection.beCode=store.beCode;
 rememberRestaurant(selection);$('storeDialog').close();
 if(openLibraryAfterStore&&!libraryPage){location.href='/library';return;}
 openLibraryAfterStore=false;document.body.classList.remove('library-gated');await checkLibrary();
},msg=>$('storeMessage').textContent=msg).finally(()=>{$('storeSelect').onchange();});
async function loadCatalog(){const data=await api('/api/catalog',{});state.menu=data;renderMenu();$('search').disabled=false;$('refresh').disabled=false;}
function showCatalogError(message){
 state.menu=null;$('search').disabled=true;$('refresh').disabled=false;$('categories').replaceChildren();
 const empty=el('div',undefined,'empty');
 empty.append(el('h3','菜单查询失败'),el('p',message||'暂时无法加载参考菜单。'));
 const retry=button('重新加载菜单',()=>busy(retry,loadCatalog,showCatalogError),'primary');
 empty.append(retry);$('products').replaceChildren(empty);
 $('menuNote').textContent='点击“重新加载菜单”或右上角“刷新菜单”重试；也可以先用最近订单生成卡牌。';
}
$('refresh').onclick=()=>busy($('refresh'),loadCatalog,showCatalogError);
$('search').oninput=renderProducts;
function renderMenu(){const nav=$('categories');nav.replaceChildren();for(const name of ['全部',...state.menu.categories.map(c=>c.name)])nav.append(button(name.replaceAll('\n',' '),()=>{state.category=name;renderMenu();},state.category===name?'active':''));$('menuNote').textContent=`${Object.keys(state.menu.meals).length} 款参考餐品 · 未优惠参考价；实际餐厅供应和价格在用卡时确认。`;renderProducts();}
function renderProducts(){if(!state.menu)return;const grid=$('products');grid.replaceChildren();const category=state.menu.categories.find(c=>c.name===state.category);const codes=category?[...new Set(category.meals.map(m=>m.code))]:Object.keys(state.menu.meals);const query=$('search').value.trim().toLowerCase();for(const code of codes){const m=state.menu.meals[code];if(!m||!m.name.toLowerCase().includes(query))continue;const card=el('article',undefined,'product');const img=el('img');img.alt=m.name;img.loading='lazy';try{const url=new URL(m.image);if(url.protocol==='https:'&&url.hostname==='menu-img.mcd.cn')img.src=url.href;}catch{}img.onerror=()=>{img.removeAttribute('src');img.alt='图片暂不可用';img.onerror=null;};card.append(img);const body=el('div',undefined,'body');body.append(el('h3',m.name));const p=el('p',undefined,'price');p.append(el('span',m.originalPrice || '未提供原价'),el('span','  未优惠参考价','meta'));body.append(p);body.append(button('选择搭配 ＋',e=>openDetail(code),'select'));card.append(body);grid.append(card);}if(!grid.children.length){const empty=el('div',undefined,'empty');empty.append(el('h3','没有找到餐品'),el('p','试试其他关键词或分类。'));grid.append(empty);}}
async function openDetail(code,index=-1){const epoch=state.epoch;const requestId=state.detailRequest=(state.detailRequest||0)+1;state.detail=null;state.editing=index;$('detailTitle').textContent='餐品配置';$('detailContent').replaceChildren(el('p','正在查询可选搭配…'));$('detailMessage').textContent='';$('addItem').disabled=true;showDialog('detailDialog');try{const data=await api('/api/catalog-detail',{code});if(epoch!==state.epoch||requestId!==state.detailRequest||!$('detailDialog').open)return;state.detail=data.detail;state.editing=index;const saved=index>=0?state.draft[index].item:null;if(saved?.needsConfiguration)data.item.quantity=saved.quantity;renderDetail(saved&&!saved.needsConfiguration?structuredClone(saved):data.item);if(saved?.needsConfiguration)$('detailMessage').textContent=`历史搭配：${summary(saved)}。下方是参考菜单的默认配置，请按原搭配逐项确认后加入。`;$('addItem').disabled=false;}catch(e){$('detailContent').replaceChildren();$('detailMessage').textContent=e.message;}}
function quantityInput(value,min,max){const input=el('input');input.type='number';input.min=String(min);if(max>=0)input.max=String(max);input.step='1';input.value=String(value);input.required=true;return input;}
// Confirmed by the user against the official menu on 2026-10-22.
// Scope this label to the verified drink and option code, not all unnamed groups.
function modificationTitle(detail,group,index){
 if(detail.code==='510479' && group.values?.length && group.values.every(option=>option.code==='8008'))return '加一份浓缩';
 return group.name || `特调 ${index+1}`;
}
function modsEditor(detail,selected){const wrapper=el('div');const getters=[];for(const [gi,group] of (detail.modification?.items||[]).entries()){const box=el('div',undefined,'mods');box.append(el('p',`${modificationTitle(detail,group,gi)} · 选 ${group.minValues}–${group.maxValues} 项`));const options=[];for(const option of group.values||[]){const selectedValue=selected?.values?.find(v=>v.code===option.code&&v.key===option.selectedKey);const count=selected?selectedValue?.quantity||0:option.selectedQuantity||0;const label=el('label');const input=quantityInput(count,0,option.maxQuantity);input.setAttribute('aria-label',`${option.name}数量`);label.append(input,el('span',option.name));box.append(label);input.oninput=()=>{if(group.maxValues===1&&Number(input.value)>0){for(const other of options){if(other.input!==input)other.input.value='0';}}};options.push({option,input});}wrapper.append(box);getters.push(()=>{const values=[];let picked=0;for(const {option,input} of options){const count=Number(input.value);if(!input.checkValidity()||!Number.isInteger(count))throw Error('特调数量必须为有效整数。');if(count>0){picked++;if(count<option.minQuantity)throw Error(`${option.name}未达到最少数量。`);}const key=count>0?option.selectedKey:option.unselectedKey;if(key!==undefined&&key!==null)values.push({code:option.code,key,quantity:count});}if(picked<group.minValues||picked>group.maxValues)throw Error(`特调需要选择 ${group.minValues}–${group.maxValues} 项。`);return values;});}return {node:wrapper,read:()=>({values:getters.flatMap(g=>g())})};}
let readDetail=null;
function renderDetail(item){const d=state.detail;const root=$('detailContent');root.replaceChildren();$('detailTitle').textContent=d.name;const qtyLabel=el('label','餐品份数');const qty=quantityInput(item.quantity,1,99);qtyLabel.append(qty);root.append(qtyLabel);const topMods=modsEditor(d,item.modification);root.append(topMods.node);const readers=[];for(const group of d.rounds||[]){const box=el('section',undefined,'round');box.append(el('h3',group.name),el('p',`本轮共选 ${group.minQuantity}–${group.maxQuantity} 份 · 更换搭配可能影响价格`,'fine'));const selected=item.roundList?.find(r=>r.round===String(group.id))?.comboItemList||[];const choiceReaders=[];for(const choice of group.choices||[]){const saved=selected.find(c=>c.code===choice.code);const row=el('div',undefined,'choice');const head=el('div',undefined,'choice-head');const label=el('label',`${choice.name} ${choice.diffPrice||''}`);const input=quantityInput(saved?.quantity||0,0,choice.maxQuantity>=0?Math.min(choice.maxQuantity,group.maxQuantity):group.maxQuantity);input.setAttribute('aria-label',`${group.name}：${choice.name}数量`);head.append(label,input);row.append(head);const mods=modsEditor(choice,saved?.modification);mods.node.hidden=Number(input.value)===0;input.oninput=()=>{if(group.maxQuantity===1&&Number(input.value)===1){for(const other of choiceReaders){if(other.input!==input){other.input.value='0';other.mods.node.hidden=true;}}}mods.node.hidden=Number(input.value)===0;};row.append(mods.node);box.append(row);choiceReaders.push({input,mods,choice});}root.append(box);readers.push(()=>{const list=[];for(const {input,mods,choice} of choiceReaders){const count=Number(input.value);if(!input.checkValidity()||!Number.isInteger(count))throw Error('套餐搭配数量无效。');if(count>0){const c={code:choice.code,name:choice.name,quantity:count};if(choice.modification)c.modification=mods.read();list.push(c);}}const total=list.reduce((s,c)=>s+c.quantity,0);if(total<group.minQuantity||total>group.maxQuantity)throw Error(`${group.name}需要选择 ${group.minQuantity}–${group.maxQuantity} 份。`);return {round:String(group.id),comboItemList:list};});}readDetail=()=>{if(!qty.checkValidity())throw Error('请填写 1–99 的整数份数。');const result={productCode:d.code,name:d.name,quantity:Number(qty.value),roundList:readers.map(r=>r())};if(d.modification)result.modification=topMods.read();return result;};}
$('addItem').onclick=()=>busy($('addItem'),async()=>{const item=readDetail();const entry={item};if(state.editing>=0)state.draft[state.editing]=entry;else state.draft.push(entry);$('detailDialog').close();renderDraft();tell('已加入这张卡。用卡时再检查餐厅供应和整单价格。');},msg=>$('detailMessage').textContent=msg);
function summary(item){const parts=(item.historyChoices||[]).map(c=>`${c.name} ×${c.quantity}`).concat((item.roundList||[]).flatMap(r=>r.comboItemList.map(c=>`${c.name} ×${c.quantity}`)));const modifications=[...(item.modification?.values||[]),...(item.roundList||[]).flatMap(r=>r.comboItemList.flatMap(c=>c.modification?.values||[]))];if(modifications.length)parts.push('已包含特调设置');if(item.needsConfiguration)parts.push('历史配置待确认');return parts.join(' · ')||'单品';}
function renderDraft(){const root=$('draft');root.replaceChildren();if(!state.draft.length)root.append(el('p','还没有餐品，去左边挑一份吧。','draft-empty'));state.draft.forEach(({item},i)=>{const row=el('div',undefined,'draft-item');row.append(el('strong',item.name),el('p',summary(item)));const actions=el('div',undefined,'actions');actions.append(button('−',()=>{if(item.quantity>1){item.quantity--;renderDraft();}}),el('span',`× ${item.quantity}`),button('＋',()=>{if(item.quantity<99){item.quantity++;renderDraft();}}),button('配置',()=>openDetail(item.productCode,i)),button('移除',()=>{state.draft.splice(i,1);renderDraft();},'remove'));row.append(actions);root.append(row);});$('saveButton').disabled=!state.draft.length||(state.presets.length>=MAX_CARDS&&!state.editingCard);}
$('saveForm').onsubmit=event=>{event.preventDefault();busy($('saveButton'),async()=>{
 document.querySelector('.workspace').inert=true;
 const payload={items:structuredClone(state.draft.map(e=>e.item)),name:$('cardName').value,tag:$('tag').value};if(state.editingCard)payload.id=state.editingCard;
 const saved=await api('/api/cards-save',payload);state.draft=[];state.editingCard=null;$('saveForm').reset();$('saveButton').textContent='保存为一张卡';
 tell(`「${payload.name}」已保存为卡牌 #${saved.id}，可到“我的卡包”选择餐厅检查。`);await loadLibrary();renderDraft();
 },tell).finally(()=>{document.querySelector('.workspace').inert=false;$('saveButton').textContent=state.editingCard?'保存修改':'保存为一张卡';renderDraft();});};
function filteredLibraryCards(){return state.tagFilter==='全部'?state.presets:state.presets.filter(card=>card.tag===state.tagFilter);}
async function loadLibrary(){const data=await api('/api/bootstrap');if(data.apiVersion!=='cards-first-1')throw Error('后台仍是旧版本，请在启动窗口按 Ctrl+C，再运行 python web_server.py，然后刷新页面。');state.csrf=data.csrf;state.presets=data.presets;if(state.tagFilter!=='全部'&&!state.presets.some(card=>card.tag===state.tagFilter))state.tagFilter='全部';$('count').textContent=`${data.presets.length} / ${MAX_CARDS}`;state.libraryIndex=Math.min(state.libraryIndex,Math.max(0,filteredLibraryCards().length-1));renderLibrary();}
function libraryOffset(index,current,total){let offset=index-current;if(offset>total/2)offset-=total;if(offset<-total/2)offset+=total;return offset;}
function libraryPositions(){const positions=new Map();document.querySelectorAll('.pack-card').forEach(card=>{const rect=card.getBoundingClientRect();positions.set(card.dataset.cardId,{rect,opacity:getComputedStyle(card).opacity});});return positions;}
function showLibraryIndex(index){if(libraryDraw.phase!=='idle')return;const total=filteredLibraryCards().length,next=(index+total)%total;if(next===state.libraryIndex)return;const positions=libraryPositions();const direction=Math.sign(libraryOffset(next,state.libraryIndex,total));state.libraryIndex=next;renderLibrary(positions,direction);}
function moveLibrary(step){if(filteredLibraryCards().length<2)return;showLibraryIndex(state.libraryIndex+step);}
function drawableLibraryIndexes(){
 const available=new Set(state.checks.filter(check=>check.status==='available').map(check=>check.id));
 return filteredLibraryCards().flatMap((card,index)=>available.has(card.id)?[index]:[]);
}
const libraryDraw={phase:'idle',token:0,duration:430};
const drawPause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function flipLibraryFaces(toBack){
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const animations=[...document.querySelectorAll('.pack-card-flipper')].map(face=>{
  face.style.transform=toBack?'rotateY(180deg)':'rotateY(0deg)';
  if(reduced||!face.animate)return Promise.resolve();
  return face.animate([{transform:toBack?'rotateY(0deg)':'rotateY(180deg)'},{transform:face.style.transform}],{duration:520,easing:'cubic-bezier(.4,0,.2,1)'}).finished.catch(()=>{});
 });
 await Promise.all(animations);
}
async function revealLibraryDraw(){
 if(libraryDraw.phase!=='waiting')return;
 const token=libraryDraw.token;
 libraryDraw.phase='revealing';
 const draw=document.querySelector('.pack-random');if(draw){draw.disabled=true;draw.textContent='正在翻牌…';}
 await flipLibraryFaces(false);
 if(token!==libraryDraw.token)return;
 libraryDraw.phase='idle';renderLibrary();
 document.querySelector('.pack-card.current')?.focus({preventScroll:true});
 $('libraryMessage').textContent='已抽中：'+filteredLibraryCards()[state.libraryIndex].name;
}
async function drawRandomLibraryCard(){
 if(libraryDraw.phase==='waiting'){await revealLibraryDraw();return;}
 if(libraryDraw.phase!=='idle')return;
 const eligible=drawableLibraryIndexes();if(!eligible.length)return;
 const target=eligible[Math.floor(Math.random()*eligible.length)];
 const total=filteredLibraryCards().length,token=++libraryDraw.token;
 libraryDraw.phase='flipping';renderLibrary(null,0,true);
 $('libraryMessage').textContent='正在翻到背面…';
 await flipLibraryFaces(true);
 if(token!==libraryDraw.token)return;
 libraryDraw.phase='rolling';
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const steps=total===1?0:total*2+(target-state.libraryIndex+total)%total;
 if(!reduced)for(let step=0;step<steps;step++){
  if(token!==libraryDraw.token)return;
  const previous=libraryPositions();
  state.libraryIndex=(state.libraryIndex+1)%total;
  libraryDraw.duration=100+260*Math.pow((step+1)/steps,3);
  renderLibrary(previous,1,true);
  $('libraryMessage').textContent='正在抽取…';
  await drawPause(libraryDraw.duration+20);
 }
 if(token!==libraryDraw.token)return;
 state.libraryIndex=target;libraryDraw.phase='waiting';renderLibrary(null,0,true);
 $('libraryMessage').textContent='已停在结果卡，点击中央卡牌揭晓。';
 document.querySelector('.pack-card.current')?.focus({preventScroll:true});
}
function animateLibraryCards(previous,direction=0){
 if(!previous||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 document.querySelectorAll('.pack-card').forEach(card=>{
  if(!card.animate)return;
  const old=previous.get(card.dataset.cardId),style=getComputedStyle(card);
  const finalTransform=style.transform==='none'?'none':style.transform;
  if(!old){
   card.animate([
    {transform:`translateX(${direction*56}px) ${finalTransform}`,filter:'brightness(1.08)'},
    {transform:finalTransform,filter:'brightness(1)'}
   ],{duration:libraryDraw.phase==='rolling'?libraryDraw.duration:430,easing:'cubic-bezier(.22,1,.36,1)'});
   return;
  }
  const current=card.getBoundingClientRect();
  const dx=old.rect.left-current.left,dy=old.rect.top-current.top;
  const sx=old.rect.width/current.width,sy=old.rect.height/current.height;
  // Animate transform rather than the individual translate property. The
  // latter is reserved for translate(-50%, -50%) and keeps every card centred.
  card.animate([
   {transform:`translate(${dx}px,${dy}px) scale(${sx},${sy}) ${finalTransform}`,opacity:old.opacity},
   {transform:finalTransform,opacity:style.opacity}
  ],{duration:libraryDraw.phase==='rolling'?libraryDraw.duration:430,easing:'cubic-bezier(.22,1,.36,1)'});
 });
}
function renderLibrary(previousPositions=null,direction=0,drawFrame=false){
 if(!drawFrame&&libraryDraw.phase!=='idle'){libraryDraw.token++;libraryDraw.phase='idle';$('libraryMessage').textContent='';}
 const drawing=libraryDraw.phase!=='idle';
 const root=$('library');root.replaceChildren();
 if(!state.presets.length){const empty=el('div',undefined,'library-empty');empty.append(el('h2','卡包还是空的'),el('p','去创建第一张卡，或用最近订单快速生成。'));root.append(empty);return;}
 const filter=el('div',undefined,'library-filter');
 const storeControl=el('div',undefined,'library-store');
 storeControl.append(el('span',`当前餐厅：${state.restaurant?.storeName||'未选择'}`,'library-store-current'));
 const changeStore=button('切换餐厅',()=>requestRestaurant(false),'outline library-store-change');changeStore.disabled=drawing;storeControl.append(changeStore);filter.append(storeControl);
 const tagLabel=el('label',undefined,'library-tag-filter');tagLabel.append(el('span','按 Tag 筛选'));const filterSelect=el('select');for(const tag of ['全部',...new Set(state.presets.map(card=>card.tag).filter(Boolean))]){const option=el('option',tag);option.value=tag;option.selected=tag===state.tagFilter;filterSelect.append(option);}filterSelect.onchange=()=>{state.tagFilter=filterSelect.value;state.libraryIndex=0;renderLibrary();};filterSelect.disabled=drawing;tagLabel.append(filterSelect);filter.append(tagLabel);root.append(filter);
 const cards=filteredLibraryCards();
 if(!cards.length){const empty=el('div',undefined,'library-empty');empty.append(el('h2','没有这个 Tag 的卡牌'),el('p','换一个 Tag，或编辑卡牌标签后再试。'));root.append(empty);return;}
 state.libraryIndex=Math.min(state.libraryIndex,cards.length-1);
 const current=cards[state.libraryIndex];
 const check=state.checks.find(c=>c.id===current.id);
 const detail=el('article',undefined,'pack-detail');
 const detailScroll=el('div',undefined,'pack-detail-scroll');
 const titleRow=el('div',undefined,'pack-title-row');titleRow.append(el('h2',current.name));if(current.tag)titleRow.append(el('span',current.tag,'pack-title-tag'));detailScroll.append(titleRow);
 const items=el('div',undefined,'pack-items');
 for(const item of current.items){const line=el('div',undefined,'pack-item');line.append(el('strong',`${item.name} ×${item.quantity}`),el('p',summary(item)));items.append(line);}
 detailScroll.append(items);
 const status=el('p',check?({available:'配置可用',adjust:'当前餐厅不可用',unknown:'仍需确认'}[check.status]):'尚未检查餐厅',`card-status ${check?.status||''}`);detailScroll.append(status);
 if(check)for(const reason of check.reasons)detailScroll.append(el('p',reason,'fine'));
 const detailActions=el('div',undefined,'pack-actions');
 const choose=button('核价并继续',()=>openCheckout(current),'primary');
 const edit=el('a','编辑','text-link pack-edit');edit.href=`/builder?card=${current.id}`;
 detailActions.append(choose,edit,button('删除卡牌',async()=>{if(!confirm(`删除「${current.name}」？`))return;try{await api('/api/delete',{id:current.id});if(state.selectedCard===current.id)state.selectedCard=null;await loadLibrary();renderDraft();}catch(e){tell(e.message);}},'pack-delete'));
 detail.append(detailScroll,detailActions);if(drawing){detail.replaceChildren(el('p','等待翻牌揭晓本次搭配','pack-draw-placeholder'));}root.append(detail);
 const viewer=el('section',undefined,'pack-viewer');viewer.setAttribute('aria-label','套餐卡牌选择器');
 const hint=el('p',drawing?(libraryDraw.phase==='waiting'?'点击中央卡牌，一起翻面揭晓':'正在抽取，请稍候…'):'滚动鼠标滚轮，切换上一张 / 下一张','pack-hint');viewer.append(hint);
 const carousel=el('div',undefined,'pack-carousel');carousel.tabIndex=0;carousel.setAttribute('role','listbox');carousel.setAttribute('aria-label','使用滚轮或左右方向键切换卡牌');
 cards.forEach((card,index)=>{const offset=libraryOffset(index,state.libraryIndex,cards.length);const distance=Math.abs(offset);if(distance>2)return;const cardButton=button('',()=>drawing?(index===state.libraryIndex&&revealLibraryDraw()):showLibraryIndex(index),`pack-card${index===state.libraryIndex?' current':''}`);cardButton.dataset.cardId=String(card.id);cardButton.style.setProperty('--slot-left',`${50+offset*17}%`);cardButton.style.setProperty('--x','0px');cardButton.style.setProperty('--card-scale',String(Math.max(.58,1-distance*.14)));cardButton.style.setProperty('--card-opacity','1');cardButton.style.setProperty('--card-wash',String(Math.min(.5,distance*.22)));cardButton.style.setProperty('--card-layer',String(20-distance));cardButton.setAttribute('role','option');cardButton.setAttribute('aria-selected',String(index===state.libraryIndex));cardButton.setAttribute('aria-label',drawing?(index===state.libraryIndex?'结果卡，点击揭晓':'背面卡牌'):`${card.name}${index===state.libraryIndex?'，当前卡牌':''}`);cardButton.tabIndex=index===state.libraryIndex?0:-1;const face=el('img');face.src=`/orbit-assets/${card.face}.png`;face.alt=`${card.name}的卡面`;face.draggable=false;const caption=el('span',card.name,'pack-card-caption');const flipper=el('span',undefined,'pack-card-flipper');const front=el('span',undefined,'pack-card-front');front.append(face,caption);const back=el('img',undefined,'pack-card-back');back.src='/orbit-assets/card-back.png';back.alt='卡牌背面';back.draggable=false;flipper.append(front,back);flipper.style.transform=drawing&&libraryDraw.phase!=='flipping'?'rotateY(180deg)':'rotateY(0deg)';front.setAttribute('aria-hidden',String(drawing));cardButton.append(flipper);carousel.append(cardButton);});
 let wheelSum=0,wheelTimer;
 carousel.addEventListener('wheel',event=>{event.preventDefault();if(Date.now()<state.wheelReadyAt)return;wheelSum+=event.deltaY||event.deltaX;clearTimeout(wheelTimer);wheelTimer=setTimeout(()=>{wheelSum=0;},180);if(Math.abs(wheelSum)>=35){state.wheelReadyAt=Date.now()+420;moveLibrary(wheelSum>0?1:-1);wheelSum=0;}},{passive:false});
 carousel.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();moveLibrary(event.key==='ArrowRight'?1:-1);}});
 viewer.append(carousel);
 const draw=button('随机抽一张',drawRandomLibraryCard,'pack-random');
 draw.disabled=drawing?libraryDraw.phase!=='waiting':drawableLibraryIndexes().length===0;
 draw.title=draw.disabled?'当前筛选下没有已确认配置可用的卡牌，请检查餐厅或调整卡牌配置':'从当前 Tag 下配置可用的卡牌中随机抽取';
 if(draw.disabled)draw.textContent='暂无可抽取的卡牌';
 if(drawing){draw.textContent=libraryDraw.phase==='waiting'?'点击翻牌揭晓':'正在抽取…';draw.title='等待滚动停稳后翻牌';}viewer.append(draw);
 const nav=el('div',undefined,'pack-nav');nav.append(button('← 上一张',()=>moveLibrary(-1),'outline'),el('span',`${state.libraryIndex+1} / ${cards.length}`),button('下一张 →',()=>moveLibrary(1),'outline'));if(drawing)nav.querySelectorAll('button').forEach(b=>b.disabled=true);viewer.append(nav);root.append(viewer);
 animateLibraryCards(previousPositions,direction);
}
$('libraryButton').onclick=()=>{if(libraryPage){location.href='/builder';return;}if(state.context)location.href='/library';else requestRestaurant(true);};
window.addEventListener('beforeunload',e=>{if(state.draft.length){e.preventDefault();e.returnValue='';}});
async function initialize(){
 const remembered=rememberedRestaurant();if(remembered)applyRestaurant(remembered);
 await loadLibrary();
 if(libraryPage){
  if(state.context)await checkLibrary();
  else{document.body.classList.add('library-gated');requestRestaurant(true);}
 }else{
  const params=new URLSearchParams(location.search),startMode=params.get('start');
  const id=Number(params.get('card'));
  if(startMode==='recent'||startMode==='custom'){params.delete('start');history.replaceState(null,'',`${location.pathname}${params.size?`?${params}`:''}${location.hash}`);}
  if(id){const card=state.presets.find(c=>c.id===id);if(card){state.editingCard=id;state.draft=structuredClone(card.items).map(item=>({item}));$('cardName').value=card.name;$('tag').value=card.tag;$('saveButton').textContent='保存修改';}else tell('这张卡不存在，请从卡包重新选择。');}
  renderDraft();
  try{await loadCatalog();}catch(e){showCatalogError(e.message);}
 }
}
initialize().catch(e=>{tell(`初始化失败：${e.message}`);$('products').replaceChildren(el('p','连接后台后才能加载参考菜单。','empty'));$('menuNote').textContent='后台未就绪';});
