'use strict';
// Each card's left (long) edge lies on a vertical cylinder generator.
// The plane extends radially outward; the entire array rotates as one object.
const fronts = [
  'burger-v1', 'wings-two-v1', 'icecream-three-v2', 'nuggets-four-v2',
  'hashbrown-five-v2', 'pies-six',
  'fries-seven', 'mcflurry-eight', 'cola-nine', 'chicken-ten',
  'ronald-king-v1', 'birdie-king-v2', 'hamburglar-king-v1', 'grimace-king-v2',
  'ronald-plaster-v1', 'ronald-front-v2',
];
const $ = (id) => document.getElementById(id);
const ring = $('ring'), stage = $('stage'), camera = $('camera');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const ROTATION_SPEED_PERCENT = 15;
const ROTATION_SPEED = ROTATION_SPEED_PERCENT; // 100% maps to 100 degrees per second.
const CYLINDER_RADIUS = 200;
const MAX_CARDS = 16;
let angle = 11, tilt = 22, pointer = null;
let lastTime = null, lastY = 0;
const background = createSwirl();
let backgroundTime = 0, lastBackgroundFrame = -Infinity;
fronts.forEach((name, i) => {
  const anchor = document.createElement('div');
  anchor.className = 'anchor';
  anchor.style.setProperty('--angle', `${i * 360 / fronts.length}deg`);
  const card = document.createElement('div');
  card.className = 'card';
  for (const side of ['front', 'back']) {
    const img = new Image();
    img.className = `face ${side}`;
    img.src = side === 'front' ? `/orbit-assets/${name}.png` : '/orbit-assets/card-back.png';
    img.alt = side === 'front' ? `卡牌 ${i + 1} 正面` : `卡牌 ${i + 1} 背面`;
    img.draggable = false;
    img.addEventListener('error', () => { $('status').textContent = '部分卡牌素材未能加载，请刷新重试。'; });
    card.append(img);
  }
  anchor.append(card);
  ring.append(anchor);
});
function paint() { ring.style.transform = `rotateY(${angle}deg)`; }
function settings() {
  ring.style.setProperty('--radius', `${CYLINDER_RADIUS}px`);
  // Bound every card through a full rotation, including its outline and
  // perspective enlargement. High viewing angles need more vertical room.
  const radians = tilt * Math.PI / 180;
  const radius = CYLINDER_RADIUS + 122, halfCardHeight = 82;
  const halfHeight = radius * Math.sin(radians) + halfCardHeight * Math.cos(radians);
  const depth = radius * Math.cos(radians) + halfCardHeight * Math.sin(radians);
  const perspective = parseFloat(getComputedStyle(stage).perspective) || 1500;
  const availableX = Math.max(1, stage.clientWidth / 2 - 16);
  const availableY = Math.max(1, stage.clientHeight / 2 - 16);
  const scale = Math.min(
    1,
    stage.clientWidth / (2 * (CYLINDER_RADIUS + 120) * 1.27),
    stage.clientHeight / 390,
    availableX / (radius + availableX * depth / perspective),
    availableY / (halfHeight + availableY * depth / perspective),
  );
  camera.style.transform = `scale3d(${scale},${scale},${scale}) rotateX(-${tilt}deg)`;
}
stage.addEventListener('pointerdown', e => {
  if (e.button !== 0 || pointer !== null) return;
  pointer = e.pointerId; lastY = e.clientY;
  stage.setPointerCapture(e.pointerId);
});
stage.addEventListener('pointermove', e => {
  if (pointer !== e.pointerId) return;
  tilt = Math.max(0, Math.min(75, tilt - (e.clientY - lastY) * .22));
  lastY = e.clientY;
  settings();
});
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
  stage.addEventListener(event, e => { if (pointer === e.pointerId) pointer = null; });
}
// Reduced motion is handled automatically; there are no animation controls.
reducedMotion.addEventListener('change', () => { lastTime = null; });
document.addEventListener('visibilitychange', () => { lastTime = null; });
new ResizeObserver(settings).observe(stage);
function tick(time) {
  if (lastTime !== null && !reducedMotion.matches && !document.hidden) {
    angle = (angle - Math.min((time - lastTime) / 1000, .1) * ROTATION_SPEED) % 360;
    backgroundTime += Math.min((time - lastTime) / 1000, .1);
    paint();
  }
  if (!document.hidden && time - lastBackgroundFrame >= 1000 / 24) {
    background.draw(backgroundTime);
    lastBackgroundFrame = time;
  }
  lastTime = time;
  requestAnimationFrame(tick);
}
settings(); paint(); requestAnimationFrame(tick);

const startButton = $('startButton');
const startDialog = $('startDialog');
$('startDialogClose').addEventListener('click', () => startDialog.close());
startButton.addEventListener('click', async () => {
  startButton.disabled = true;
  try {
    await window.mcpCredentials.ensure();
    startDialog.showModal();
  } catch (error) {
    if (error.message !== '请先接入自己的 MCP Token。') {
      $('status').textContent = `无法开始：${error.message}`;
    }
  } finally {
    startButton.disabled = false;
  }
});
startDialog.addEventListener('click', event => {
  if (event.target === startDialog) startDialog.close();
});
const recentResultDialog = $('recentResultDialog');
const recentResultView = $('recentResultView');
$('recentResultClose').addEventListener('click', () => recentResultDialog.close());
recentResultView.addEventListener('click', () => { location.href = recentResultView.dataset.target || '/library'; });
recentResultDialog.addEventListener('click', event => {
  if (event.target === recentResultDialog) recentResultDialog.close();
});
function showRecentResult(success, error='', actionLabel='查看', actionTarget='/library') {
  $('recentResultEyebrow').textContent = success ? '创建完成' : '创建未完成';
  $('recentResultTitle').textContent = success ? '已从最近订单生成卡牌' : '最近订单生成失败';
  const errorLine = $('recentResultError');
  errorLine.textContent = error;
  errorLine.hidden = success;
  recentResultView.textContent = actionLabel;
  recentResultView.dataset.target = actionTarget;
  recentResultView.disabled = false;
  startDialog.close();
  recentResultDialog.showModal();
}
$('recentStart').addEventListener('click', async event => {
  const button = event.currentTarget;
  const message = $('recentStartMessage');
  button.disabled = true;
  message.textContent = '正在读取你的最近订单…';
  try {
    await window.mcpCredentials.ensure();
    const bootstrapResponse = await fetch('/api/bootstrap');
    const bootstrap = await bootstrapResponse.json();
    if (!bootstrapResponse.ok) throw Error(bootstrap.error || '无法连接后台，请重试。');
    if ((bootstrap.presets?.length || 0) >= MAX_CARDS) {
      message.textContent = '';
      showRecentResult(false, `卡牌数量已达到上限（${MAX_CARDS} 张），请先删除不需要的卡牌。`, '查看卡包', '/library');
      return;
    }
    const response = await fetch('/api/quick-start', {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRF-Token':bootstrap.csrf},
      body: '{}',
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || '最近订单生成失败，请重试。');
    if (!result.created.length) {
      message.textContent = '';
      if (result.capacity === 0) showRecentResult(false, `卡牌数量已达到上限（${MAX_CARDS} 张），请先删除不需要的卡牌。`, '查看卡包', '/library');
      else showRecentResult(false, '没有生成新卡。最近订单均已生成过，或没有可用的已完成订单。', '自定义创建', '/builder');
      return;
    }
    message.textContent = '';
    showRecentResult(true);
  } catch (error) {
    message.textContent = '';
    showRecentResult(false, `生成失败：${error.message}`, '自定义创建', '/builder');
  } finally {
    button.disabled = false;
  }
});

// A low-resolution fragment shader: polar twist + repeated sine domain warping.
// The canvas is decorative and never receives pointer input.
function createSwirl() {
  const canvas = $('swirl');
  let gl;
  try { gl = canvas.getContext('webgl', {alpha:false, antialias:false, depth:false, powerPreference:'low-power'}); } catch {}
  const fallback = {draw(){}};
  if (!gl) { canvas.hidden = true; return fallback; }
  const vertex = `attribute vec2 point; void main(){gl_Position=vec4(point,0.0,1.0);}`;
  const fragment = `
    precision mediump float;
    uniform vec2 size;
    uniform float time;
    void main(){
      vec2 uv=gl_FragCoord.xy/size;
      vec2 p=(gl_FragCoord.xy-.5*size)/size.y;
      float r=length(p);
      float a=r*4.0-time*.065;
      float c=cos(a),s=sin(a);
      p=mat2(c,-s,s,c)*p;
      for(int i=0;i<5;i++){
        p+=.43*sin(p.yx*1.65+time*.045+float(i)*.65);
      }
      float wave=.5+.5*sin(p.x*3.6+p.y*.6);
      vec3 red=mix(vec3(.69,.015,.035),vec3(.91,.04,.065),wave);
      float white=smoothstep(.66,.79,wave);
      vec3 color=mix(red,vec3(1.0,.96,.89),white*.90);
      // Quiet central reading area, broad white ribbons at the edges.
      float center=1.0-smoothstep(.10,.50,abs(uv.x-.5));
      float reading=1.0-smoothstep(.12,.40,abs(uv.x-.5));
      float top=smoothstep(.65,.92,uv.y);
      float bottom=1.0-smoothstep(.08,.33,uv.y);
      float veil=max(center*.60,reading*max(top,bottom)*.84);
      color=mix(color,vec3(.76,.015,.035),veil);
      gl_FragColor=vec4(color,1.0);
    }`;
  let program;
  function compile(type, source){
    const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){gl.deleteShader(shader);throw Error('shader compilation');}
    return shader;
  }
  try {
    const vs=compile(gl.VERTEX_SHADER,vertex), fs=compile(gl.FRAGMENT_SHADER,fragment);
    program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
    gl.deleteShader(vs);gl.deleteShader(fs);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('shader linking');
  } catch {canvas.hidden=true;return fallback;}
  gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  const point=gl.getAttribLocation(program,'point');gl.enableVertexAttribArray(point);gl.vertexAttribPointer(point,2,gl.FLOAT,false,0,0);
  const size=gl.getUniformLocation(program,'size'), time=gl.getUniformLocation(program,'time');
  let dirty=true, previousTime=null, lost=false;
  const resize=()=>{dirty=true;};window.addEventListener('resize',resize);
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true;canvas.hidden=true;});
  return {draw(t){
    if(lost||(!dirty&&t===previousTime))return;
    if(dirty){
      // Roughly four CSS pixels per shader pixel; cap work on large monitors.
      const factor=Math.max(4,window.innerWidth/480);
      canvas.width=Math.max(1,Math.round(window.innerWidth/factor));
      canvas.height=Math.max(1,Math.round(window.innerHeight/factor));
      gl.viewport(0,0,canvas.width,canvas.height);gl.uniform2f(size,canvas.width,canvas.height);dirty=false;
    }
    gl.uniform1f(time,t);gl.drawArrays(gl.TRIANGLES,0,6);previousTime=t;
  }};
}
