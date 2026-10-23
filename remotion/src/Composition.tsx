import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';

export type StepKey = 'connect' | 'choose' | 'save' | 'review' | 'draw';

const RED = '#d9000d';
const DARK_RED = '#9f0010';
const YELLOW = '#ffbc0d';
const INK = '#241b13';
const PAPER = '#fffaf0';

const copy: Record<StepKey, {number: string; title: string; subtitle: string}> = {
  connect: {number: '01', title: '接入你的麦当劳 MCP', subtitle: '点击「快速开始」，使用个人 API Key 安全连接'},
  choose: {number: '02', title: '选择你的建卡方式', subtitle: '最近订单一键生成，或从菜单自由搭配'},
  save: {number: '03', title: '把喜欢的搭配存成卡', subtitle: '选择餐品与配置，为这张卡命名并收藏'},
  review: {number: '04', title: '在卡包里检阅方案', subtitle: '切换卡牌、查看餐品，并按实际餐厅检查可用性'},
  draw: {number: '05', title: '随机抽卡，决定这一餐', subtitle: '所有卡牌翻到背面，滚动停稳后点击揭晓'},
};

const Window: React.FC<{children: React.ReactNode; label: string}> = ({children, label}) => (
  <div style={{width: 760, height: 590, borderRadius: 28, background: '#fff', border: '7px solid #fff', boxShadow: '0 28px 70px rgba(74,0,6,.2)', overflow: 'hidden'}}>
    <div style={{height: 64, display: 'flex', alignItems: 'center', gap: 13, padding: '0 24px', background: '#f5f1e8', borderBottom: '2px solid #e8dfce'}}>
      {['#ef5a54', '#f6be38', '#4fbd61'].map((color) => <span key={color} style={{width: 17, height: 17, borderRadius: '50%', background: color}} />)}
      <span style={{marginLeft: 15, fontSize: 17, fontWeight: 750, color: '#6b6259'}}>{label}</span>
    </div>
    <div style={{height: 526, position: 'relative', background: PAPER}}>{children}</div>
  </div>
);

const Card: React.FC<{src: string; width?: number; rotate?: number; opacity?: number; outline?: boolean}> = ({src, width = 170, rotate = 0, opacity = 1, outline = false}) => (
  <div style={{width, aspectRatio: '1089 / 1445', rotate: `${rotate}deg`, opacity, borderRadius: 13, overflow: 'hidden', background: '#fff', boxShadow: outline ? `0 0 0 8px ${YELLOW}, 0 22px 45px #5a350040` : '0 18px 38px #5a350035'}}>
    <Img src={staticFile(src)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
  </div>
);

const ConnectVisual: React.FC = () => (
  <Window label="McCard · 快速开始">
    <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(145deg,#fff 0%,#fff8e3 100%)'}} />
    <div style={{position: 'absolute', left: 92, top: 48, width: 575, padding: '34px 38px', borderRadius: 20, background: '#fff', boxShadow: '0 18px 55px #4f351525', borderTop: `8px solid ${YELLOW}`}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
        <Img src={staticFile('brand/logo.svg')} style={{width: 105, height: 78}} />
        <div><div style={{fontSize: 29, fontWeight: 900, color: INK}}>接入你的麦当劳账号</div><div style={{fontSize: 16, color: '#76685a', marginTop: 7}}>使用个人 MCP API Key 连接</div></div>
      </div>
      <div style={{marginTop: 28, fontSize: 15, fontWeight: 750, color: DARK_RED}}>前往麦当劳官方申请 MCP API Key ↗</div>
      <div style={{marginTop: 20, fontSize: 14, fontWeight: 700, color: '#55493d'}}>个人 MCP API Key</div>
      <div style={{height: 52, marginTop: 9, padding: '0 17px', border: '2px solid #c9bca9', borderRadius: 8, display: 'flex', alignItems: 'center', color: '#827566', letterSpacing: 8, fontSize: 21}}>••••••••••••••••</div>
      <div style={{display: 'flex', justifyContent: 'flex-end', marginTop: 24}}><div style={{padding: '14px 28px', borderRadius: 8, background: YELLOW, fontWeight: 900, color: '#382900'}}>接入并继续</div></div>
    </div>
    <div style={{position: 'absolute', left: 76, bottom: 20, fontSize: 14, color: '#7b6d5e'}}>密钥只保存在服务器会话内，不写入项目文件</div>
  </Window>
);

const ChoiceVisual: React.FC = () => (
  <Window label="McCard · 创建卡牌">
    <div style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at 50% 42%,#ef2630 0,${RED} 62%,${DARK_RED} 100%)`}} />
    <div style={{position: 'absolute', left: 50, top: 35, color: '#fff', opacity: .3, fontSize: 25, fontWeight: 900}}>把喜欢的组合，存成一张牌</div>
    <div style={{position: 'absolute', inset: 0, background: '#24000599'}} />
    <div style={{position: 'absolute', left: 88, top: 35, width: 584, borderTop: `7px solid ${YELLOW}`, borderRadius: 13, background: '#fff', color: '#242424', boxShadow: '0 25px 70px #38000670', overflow: 'hidden'}}>
      <div style={{display: 'flex', justifyContent: 'space-between', padding: '25px 29px 16px'}}>
        <div><div style={{fontSize: 13, fontWeight: 800, color: '#ba000d'}}>快速开始</div><div style={{fontSize: 27, fontWeight: 900, marginTop: 5}}>想怎么创建这张卡？</div></div>
        <div style={{fontSize: 34, lineHeight: 1, color: '#333'}}>×</div>
      </div>
      <div style={{padding: '0 29px 28px', display: 'grid', gap: 13}}>
        <div style={{padding: '18px 20px', border: `2px solid ${YELLOW}`, borderRadius: 8, background: '#fff6d5'}}><div style={{fontSize: 19, fontWeight: 900}}>从最近订单生成</div><div style={{fontSize: 13, color: '#5b5b5b', marginTop: 6}}>读取最近 10 笔订单，生成最多 3 张不重复卡牌</div></div>
        <div style={{padding: '18px 20px', border: '2px solid #e3e3e3', borderRadius: 8, background: '#fff'}}><div style={{fontSize: 19, fontWeight: 900}}>自定义创建</div><div style={{fontSize: 13, color: '#5b5b5b', marginTop: 6}}>从参考菜单挑选餐品，自由组合一张新卡</div></div>
      </div>
    </div>
  </Window>
);

const SaveVisual: React.FC = () => (
  <Window label="McCard · 自定义创建">
    <div style={{height: '100%', padding: '18px 24px 22px', color: '#2d2d2d', background: '#fff'}}>
      <div style={{fontSize: 11, color: '#666'}}>先收藏搭配，用卡时再选餐厅</div><div style={{fontSize: 26, fontWeight: 900, marginTop: 2}}>创建你的 McCard</div><div style={{fontSize: 12, color: '#555', marginTop: 4}}>从参考菜单自由搭配，保存你喜欢的组合。</div>
      <div style={{height: 1, background: '#e4e4e4', margin: '17px 0'}} />
      <div style={{display: 'grid', gridTemplateColumns: '1.7fr .82fr', gap: 22, height: 372}}>
        <div>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'end'}}><div><div style={{fontSize: 11, color: '#666'}}>按你的口味来</div><div style={{fontSize: 23, fontWeight: 900}}>挑选你的餐品</div></div><div style={{padding: '7px 11px', border: '1px solid #bbb', borderRadius: 4, fontSize: 11}}>刷新菜单</div></div>
          <div style={{height: 40, marginTop: 13, borderRadius: 4, background: '#f7f7f7', color: '#8a8a8a', display: 'flex', alignItems: 'center', padding: '0 13px', fontSize: 12}}>搜索汉堡、小食、饮品…</div>
          <div style={{display: 'flex', gap: 7, marginTop: 11}}>{['推荐', '汉堡', '小食', '饮品'].map((name, index) => <span key={name} style={{padding: '5px 10px', borderRadius: 20, background: index === 0 ? RED : '#f1f1f1', color: index === 0 ? '#fff' : '#555', fontSize: 10, fontWeight: 800}}>{name}</span>)}</div>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 9, marginTop: 12}}>{[["🍔", '巨无霸'], ["🍟", '中薯条'], ["🥤", '可乐中杯']].map(([icon, name]) => <div key={name} style={{height: 126, border: '1px solid #e4e4e4', borderRadius: 6, padding: 10, background: '#fff'}}><div style={{height: 63, display: 'grid', placeItems: 'center', background: '#fafafa', fontSize: 39}}>{icon}</div><div style={{fontSize: 12, fontWeight: 850, marginTop: 7}}>{name}</div><div style={{fontSize: 9, color: '#777'}}>查看配置并加入</div></div>)}</div>
        </div>
        <div style={{padding: '17px 16px', borderTop: `5px solid ${YELLOW}`, borderRadius: 5, background: '#fafafa', boxShadow: '0 4px 18px #00000012'}}>
          <div style={{fontSize: 11, color: '#9c0008', fontWeight: 800}}>我的搭配</div><div style={{fontSize: 21, fontWeight: 900, marginTop: 3}}>今天，就吃这一套</div><div style={{fontSize: 10, color: '#666', marginTop: 5}}>可添加多个餐品，搭配和特调一起保存。</div>
          <div style={{marginTop: 14, borderRadius: 4, background: '#f1f1f1', padding: '12px 11px', fontSize: 11}}><b>巨无霸 ×1</b><div style={{color: '#777'}}>默认搭配</div></div>
          <div style={{marginTop: 12, fontSize: 10, fontWeight: 800}}>卡牌名称</div><div style={{height: 39, border: '1px solid #bbb', borderRadius: 4, background: '#fff', padding: '9px 10px', color: '#777', fontSize: 11}}>比如：工作日快乐午餐</div>
          <div style={{marginTop: 11, padding: '10px 12px', textAlign: 'center', borderRadius: 4, background: RED, color: '#fff', fontSize: 12, fontWeight: 900}}>保存为一张卡</div>
        </div>
      </div>
    </div>
  </Window>
);

const ReviewVisual: React.FC = () => (
  <Window label="McCard · 我的卡包">
    <div style={{height: '100%', background: YELLOW, position: 'relative', overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 40, right: 40, top: 38, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div><div style={{fontSize: 14, color: '#705500', fontWeight: 800}}>我的卡包</div><div style={{fontSize: 29, fontWeight: 950, color: INK}}>滑动检阅你的常点方案</div></div>
        <div style={{padding: '10px 18px', background: '#fff4c9', borderRadius: 10, color: '#6c5100', fontWeight: 800}}>Tag：全部</div>
      </div>
      <div style={{position: 'absolute', left: 42, right: 42, top: 150, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9}}>
        <Card src="cards/front/icecream-three-v2.png" width={155} rotate={-9} opacity={0.55} /><Card src="cards/front/fries-seven.png" width={190} rotate={-4} opacity={0.85} /><Card src="cards/front/cola-nine.png" width={225} outline /><Card src="cards/front/icecream-three-v2.png" width={190} rotate={4} opacity={0.85} /><Card src="cards/front/fries-seven.png" width={155} rotate={9} opacity={0.55} />
      </div>
      <div style={{position: 'absolute', left: 205, right: 205, bottom: 24, height: 48, borderRadius: 12, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, fontSize: 14, fontWeight: 850, color: INK}}><span style={{color: '#176134'}}>● 配置可用</span><span>查看餐品</span><span>核价并继续</span></div>
    </div>
  </Window>
);

const DrawVisual: React.FC<{frame: number}> = ({frame}) => (
  <Window label="McCard · 随机抽卡">
    <div style={{height: '100%', background: YELLOW, position: 'relative', overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 32, top: 25, right: 32, display: 'flex', gap: 8}}>{['1  点击「随机抽一张」', '2  等待卡背滚动停稳', '3  点击中央卡牌揭晓'].map((line, index) => <div key={line} style={{flex: 1, padding: '11px 10px', borderRadius: 8, background: index === 0 ? RED : '#fff3c5', color: index === 0 ? '#fff' : INK, fontSize: 12, fontWeight: 900, textAlign: 'center'}}>{line}</div>)}</div>
      <div style={{position: 'absolute', left: 36, top: 105, fontSize: 24, fontWeight: 950, color: INK}}>从当前 Tag 下配置可用的卡牌中抽取</div>
      <div style={{position: 'absolute', left: 42, top: 192, display: 'flex', alignItems: 'center', gap: 5}}><Card src="cards/back/card-back.png" width={135} rotate={-8} opacity={0.65} /><Card src="cards/back/card-back.png" width={165} rotate={-3} /><Card src="cards/back/card-back.png" width={190} outline /></div>
      <div style={{position: 'absolute', left: 405, top: 296, fontSize: 46, fontWeight: 950, color: DARK_RED}}>→</div>
      <div style={{position: 'absolute', right: 54, top: 164, scale: interpolate(frame, [0, 48], [0.82, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)})}}><Card src="cards/front/fries-seven.png" width={220} outline /></div>
      <div style={{position: 'absolute', right: 61, bottom: 17, width: 226, textAlign: 'center', padding: '12px 0', borderRadius: 8, background: RED, color: '#fff', fontSize: 15, fontWeight: 950}}>今晚就吃这一张</div>
    </div>
  </Window>
);

const Visual: React.FC<{step: StepKey; frame: number}> = ({step, frame}) => {
  if (step === 'connect') return <ConnectVisual />;
  if (step === 'choose') return <ChoiceVisual />;
  if (step === 'save') return <SaveVisual />;
  if (step === 'review') return <ReviewVisual />;
  return <DrawVisual frame={frame} />;
};

export const StepGraphic: React.FC<{step: StepKey}> = ({step}) => {
  const frame = useCurrentFrame();
  const item = copy[step];
  return (
    <AbsoluteFill style={{fontFamily: '"Microsoft YaHei", "PingFang SC", Arial, sans-serif', color: '#fff', background: `radial-gradient(circle at 18% 14%,#f52832 0,${RED} 36%,${DARK_RED} 100%)`, overflow: 'hidden'}}>
      <div style={{position: 'absolute', width: 620, height: 620, border: '3px solid #ffffff24', borderRadius: '50%', left: -260, top: -270}} />
      <div style={{position: 'absolute', width: 360, height: 360, border: '3px solid #ffffff18', borderRadius: '50%', right: -120, bottom: -170}} />
      <div style={{position: 'absolute', left: 70, top: 50, display: 'flex', alignItems: 'center', gap: 15}}>
        <div style={{padding: 8, border: '4px solid #fff', borderRadius: 14}}><Img src={staticFile('brand/logo.svg')} style={{width: 98, height: 72}} /></div>
        <div><div style={{fontSize: 31, fontWeight: 950}}>McCard</div><div style={{fontSize: 13, color: '#ffd8ce'}}>把常点套餐收藏成卡</div></div>
      </div>
      <div style={{position: 'absolute', left: 72, top: 225, width: 610, opacity: interpolate(frame, [0, 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translate: interpolate(frame, [0, 24], ['-35px 0px', '0px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)})}}>
        <div style={{display: 'inline-flex', alignItems: 'center', gap: 12, padding: '10px 17px', border: '2px solid #ffffff70', borderRadius: 99, fontSize: 16, fontWeight: 800}}><span style={{color: YELLOW}}>STEP</span><span>{item.number}</span></div>
        <h1 style={{fontSize: 61, lineHeight: 1.16, letterSpacing: -2, margin: '28px 0 22px', fontWeight: 950}}>{item.title}</h1>
        <p style={{fontSize: 23, lineHeight: 1.75, color: '#ffe3dc', margin: 0, maxWidth: 560}}>{item.subtitle}</p>
        <div style={{width: 95, height: 8, borderRadius: 10, background: YELLOW, marginTop: 36}} />
      </div>
      <div style={{position: 'absolute', right: 70, top: 155, opacity: interpolate(frame, [6, 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translate: interpolate(frame, [6, 30], ['45px 0px', '0px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)})}}><Visual step={step} frame={frame} /></div>
      <div style={{position: 'absolute', left: 72, bottom: 48, fontSize: 14, color: '#ffcbc5'}}>基于麦当劳 MCP · 非麦当劳官方产品</div>
    </AbsoluteFill>
  );
};
