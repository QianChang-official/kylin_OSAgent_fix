import{ae as s,ag as S,ai as B,aj as ae,b3 as ne,b4 as de,d as I,U as ie,ao as ue,aq as H,ap as ce,ar as ve,x as N,ba as be,at as M,c as v,F as T,n as P,g as $,u as o,o as a,a as e,y as pe,h as w,t as l,f as c,w as u,k as _,q,r as z,e as me,N as ge,G as he,H as fe,B as R,v as V,b8 as _e,I as j,L as ye,i as A,p as O,J as ke,s as F,aV as Ce,O as xe}from"./index--55wUsWM.js";import{_ as we}from"./PageHeader.vue_vue_type_script_setup_true_lang-DT_bCEp2.js";import{N as E}from"./Empty-CWU03Lvs.js";import{N as ze}from"./Alert-Bd15w33r.js";import{N as Te}from"./Input-Dl40Qjhg.js";import{N as $e,a as qe}from"./CollapseItem-CLoJxwG3.js";import"./use-locale-BbRixtGa.js";const Ne=s([S("table",`
 font-size: var(--n-font-size);
 font-variant-numeric: tabular-nums;
 line-height: var(--n-line-height);
 width: 100%;
 border-radius: var(--n-border-radius) var(--n-border-radius) 0 0;
 text-align: left;
 border-collapse: separate;
 border-spacing: 0;
 overflow: hidden;
 background-color: var(--n-td-color);
 border-color: var(--n-merged-border-color);
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 --n-merged-border-color: var(--n-border-color);
 `,[s("th",`
 white-space: nowrap;
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 text-align: inherit;
 padding: var(--n-th-padding);
 vertical-align: inherit;
 text-transform: none;
 border: 0px solid var(--n-merged-border-color);
 font-weight: var(--n-th-font-weight);
 color: var(--n-th-text-color);
 background-color: var(--n-th-color);
 border-bottom: 1px solid var(--n-merged-border-color);
 border-right: 1px solid var(--n-merged-border-color);
 `,[s("&:last-child",`
 border-right: 0px solid var(--n-merged-border-color);
 `)]),s("td",`
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 padding: var(--n-td-padding);
 color: var(--n-td-text-color);
 background-color: var(--n-td-color);
 border: 0px solid var(--n-merged-border-color);
 border-right: 1px solid var(--n-merged-border-color);
 border-bottom: 1px solid var(--n-merged-border-color);
 `,[s("&:last-child",`
 border-right: 0px solid var(--n-merged-border-color);
 `)]),B("bordered",`
 border: 1px solid var(--n-merged-border-color);
 border-radius: var(--n-border-radius);
 `,[s("tr",[s("&:last-child",[s("td",`
 border-bottom: 0 solid var(--n-merged-border-color);
 `)])])]),B("single-line",[s("th",`
 border-right: 0px solid var(--n-merged-border-color);
 `),s("td",`
 border-right: 0px solid var(--n-merged-border-color);
 `)]),B("single-column",[s("tr",[s("&:not(:last-child)",[s("td",`
 border-bottom: 0px solid var(--n-merged-border-color);
 `)])])]),B("striped",[s("tr:nth-of-type(even)",[s("td","background-color: var(--n-td-color-striped)")])]),ae("bottom-bordered",[s("tr",[s("&:last-child",[s("td",`
 border-bottom: 0px solid var(--n-merged-border-color);
 `)])])])]),ne(S("table",`
 background-color: var(--n-td-color-modal);
 --n-merged-border-color: var(--n-border-color-modal);
 `,[s("th",`
 background-color: var(--n-th-color-modal);
 `),s("td",`
 background-color: var(--n-td-color-modal);
 `)])),de(S("table",`
 background-color: var(--n-td-color-popover);
 --n-merged-border-color: var(--n-border-color-popover);
 `,[s("th",`
 background-color: var(--n-th-color-popover);
 `),s("td",`
 background-color: var(--n-td-color-popover);
 `)]))]),Be=Object.assign(Object.assign({},H.props),{bordered:{type:Boolean,default:!0},bottomBordered:{type:Boolean,default:!0},singleLine:{type:Boolean,default:!0},striped:Boolean,singleColumn:Boolean,size:String}),Re=I({name:"Table",props:Be,setup(p){const{mergedClsPrefixRef:d,inlineThemeDisabled:g,mergedRtlRef:b,mergedComponentPropsRef:n}=ue(p),m=N(()=>{var y,f;return p.size||((f=(y=n?.value)===null||y===void 0?void 0:y.Table)===null||f===void 0?void 0:f.size)||"medium"}),h=H("Table","-table",Ne,be,p,d),x=ce("Table",b,d),i=N(()=>{const y=m.value,{self:{borderColor:f,tdColor:C,tdColorModal:r,tdColorPopover:t,thColor:L,thColorModal:K,thColorPopover:D,thTextColor:J,tdTextColor:U,borderRadius:G,thFontWeight:W,lineHeight:Q,borderColorModal:X,borderColorPopover:Y,tdColorStriped:Z,tdColorStripedModal:ee,tdColorStripedPopover:re,[M("fontSize",y)]:te,[M("tdPadding",y)]:oe,[M("thPadding",y)]:le},common:{cubicBezierEaseInOut:se}}=h.value;return{"--n-bezier":se,"--n-td-color":C,"--n-td-color-modal":r,"--n-td-color-popover":t,"--n-td-text-color":U,"--n-border-color":f,"--n-border-color-modal":X,"--n-border-color-popover":Y,"--n-border-radius":G,"--n-font-size":te,"--n-th-color":L,"--n-th-color-modal":K,"--n-th-color-popover":D,"--n-th-font-weight":W,"--n-th-text-color":J,"--n-line-height":Q,"--n-td-padding":oe,"--n-th-padding":le,"--n-td-color-striped":Z,"--n-td-color-striped-modal":ee,"--n-td-color-striped-popover":re}}),k=g?ve("table",N(()=>m.value[0]),i,p):void 0;return{rtlEnabled:x,mergedClsPrefix:d,cssVars:g?void 0:i,themeClass:k?.themeClass,onRender:k?.onRender}},render(){var p;const{mergedClsPrefix:d}=this;return(p=this.onRender)===null||p===void 0||p.call(this),ie("table",{class:[`${d}-table`,this.themeClass,{[`${d}-table--rtl`]:this.rtlEnabled,[`${d}-table--bottom-bordered`]:this.bottomBordered,[`${d}-table--bordered`]:this.bordered,[`${d}-table--single-line`]:this.singleLine,[`${d}-table--single-column`]:this.singleColumn,[`${d}-table--striped`]:this.striped}],style:this.cssVars},this.$slots)}}),Pe={key:0,class:"trace-timeline"},Le={class:"trace-rail"},Se={key:0,class:"trace-line"},Me={class:"trace-content"},Ve={class:"trace-title-row"},Ee=I({__name:"TraceTimeline",props:{items:{}},setup(p){function d(g){const b=String(g||"").toLowerCase();return b==="success"||b==="completed"?"success":b==="warning"||b==="skipped"?"warning":b==="error"||b==="failed"||b==="blocked"?"error":"info"}return(g,b)=>p.items?.length?(a(),v("div",Pe,[(a(!0),v(T,null,P(p.items,(n,m)=>(a(),v("div",{key:`${n.title}-${m}`,class:"trace-item"},[e("div",Le,[e("span",{class:pe(["trace-dot",`trace-${d(n.status)}`])},null,2),m<p.items.length-1?(a(),v("span",Se)):w("",!0)]),e("div",Me,[e("div",Ve,[e("strong",null,l(n.title),1),c(o(q),{size:"small",type:d(n.status),bordered:!1},{default:u(()=>[_(l(n.status||"已记录"),1)]),_:2},1032,["type"])]),e("p",null,l(n.description||"该阶段未返回更多说明。"),1)])]))),128))])):(a(),$(o(E),{key:1,description:"暂无可展示的审计时间线"}))}}),Ie={class:"section-block panel"},je={key:0,class:"audit-table-wrap"},Ae={key:1,class:"audit-mobile-list"},Oe={class:"audit-card-head"},Fe={class:"section-block panel"},He={class:"form-actions"},Ke={key:1,class:"section-block grid-2"},De={class:"panel"},Je={class:"data-list"},Ue={class:"data-row"},Ge={class:"data-row"},We={class:"data-row"},Qe={class:"data-row"},Xe={class:"data-row"},Ye={class:"data-row"},Ze={class:"rule-strip"},er={class:"panel"},rr={key:2,class:"section-block panel"},ir=I({__name:"AuditView",setup(p){const d=ye(),g=z(!0),b=z(!1),n=z(""),m=z([]),h=z(String(d.query.request_id||"")),x=z(null),i=N(()=>x.value?.audit||m.value.find(C=>C.request_id===h.value)||null),k=N(()=>i.value?xe(i.value):[]);async function y(){g.value=!0,n.value="";try{m.value=await A.auditLogs(20)}catch(C){n.value=C instanceof Error?C.message:"审计日志加载失败"}finally{g.value=!1}}async function f(C=h.value){const r=C.trim();if(r){h.value=r,b.value=!0,n.value="";try{x.value=await A.auditTrace(r)}catch(t){n.value=t instanceof Error?t.message:"审计证据链加载失败"}finally{b.value=!1}}}return me(async()=>{await y(),h.value&&await f(h.value)}),(C,r)=>(a(),v(T,null,[c(we,{eyebrow:"Audit trace",title:"审计追踪",description:"每一次智能运维请求都会生成 request_id，可回放接收请求、风险判断、工具规划、执行状态和审计保存过程。"},{actions:u(()=>[c(o(R),{secondary:"",loading:g.value,onClick:y},{default:u(()=>[...r[3]||(r[3]=[_("刷新日志",-1)])]),_:1},8,["loading"])]),_:1}),n.value?(a(),$(o(ze),{key:0,class:"section-block",type:"error",title:"审计数据不可用",bordered:!1},{default:u(()=>[_(l(n.value),1)]),_:1})):w("",!0),e("section",Ie,[r[7]||(r[7]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"最近操作记录"),e("p",null,"展示真实审计日志，可选择任意 request_id 查看证据链。")])],-1)),c(o(ge),{show:g.value},{default:u(()=>[m.value.length?(a(),v("div",je,[c(o(Re),{size:"small",bordered:!1},{default:u(()=>[r[5]||(r[5]=e("thead",null,[e("tr",null,[e("th",null,"时间"),e("th",null,"请求摘要"),e("th",null,"风险"),e("th",null,"安全决策"),e("th",null,"执行状态"),e("th",null,"工具"),e("th",null,"request_id"),e("th",null,"操作")])],-1)),e("tbody",null,[(a(!0),v(T,null,P(m.value,t=>(a(),v("tr",{key:t.request_id},[e("td",null,l(o(O)(t.created_at||t.timestamp)),1),e("td",null,l(t.user_input||t.intent||"受控工具调用"),1),e("td",null,[c(o(q),{size:"small",type:o(ke)(t.risk_score),bordered:!1},{default:u(()=>[_(l(t.risk_score??0)+" / 100",1)]),_:2},1032,["type"])]),e("td",null,[c(o(q),{size:"small",type:o(F)(t.security_decision),bordered:!1},{default:u(()=>[_(l(o(V)(t.security_decision)),1)]),_:2},1032,["type"])]),e("td",null,l(o(j)(t)),1),e("td",null,l(t.selected_tool||"未选择工具"),1),e("td",null,[e("code",null,l(t.request_id),1)]),e("td",null,[c(o(R),{size:"small",text:"",type:"primary",onClick:L=>f(t.request_id)},{default:u(()=>[...r[4]||(r[4]=[_("查看证据链",-1)])]),_:1},8,["onClick"])])]))),128))])]),_:1})])):w("",!0),m.value.length?(a(),v("div",Ae,[(a(!0),v(T,null,P(m.value,t=>(a(),v("article",{key:t.request_id,class:"audit-card"},[e("div",Oe,[e("strong",null,l(t.user_input||t.intent||"受控工具调用"),1),c(o(q),{size:"small",type:o(F)(t.security_decision),bordered:!1},{default:u(()=>[_(l(o(V)(t.security_decision)),1)]),_:2},1032,["type"])]),e("p",null,l(o(O)(t.created_at||t.timestamp)),1),e("p",null,l(t.request_id),1),c(o(R),{size:"small",secondary:"",type:"primary",onClick:L=>f(t.request_id)},{default:u(()=>[...r[6]||(r[6]=[_("查看证据链",-1)])]),_:1},8,["onClick"])]))),128))])):w("",!0),!m.value.length&&!g.value?(a(),$(o(E),{key:2,description:"暂无审计日志"})):w("",!0)]),_:1},8,["show"])]),e("section",Fe,[r[9]||(r[9]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"证据链查询"),e("p",null,"输入 request_id 后回放单次请求的安全执行链路。")])],-1)),e("div",He,[c(o(Te),{value:h.value,"onUpdate:value":r[0]||(r[0]=t=>h.value=t),placeholder:"输入 request_id",onKeydown:r[1]||(r[1]=he(fe(t=>f(),["prevent"]),["enter"]))},null,8,["value"]),c(o(R),{type:"primary",loading:b.value,disabled:!h.value.trim(),onClick:r[2]||(r[2]=t=>f())},{default:u(()=>[...r[8]||(r[8]=[_("查看证据链",-1)])]),_:1},8,["loading","disabled"])])]),x.value?(a(),v("section",Ke,[e("div",De,[r[18]||(r[18]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"审计摘要"),e("p",null,"以人类可读方式展示本次操作的关键结论。")])],-1)),i.value?(a(),v(T,{key:0},[e("div",Je,[e("div",Ue,[r[10]||(r[10]=e("span",null,"request_id",-1)),e("strong",null,l(i.value.request_id||h.value),1)]),e("div",Ge,[r[11]||(r[11]=e("span",null,"请求内容",-1)),e("strong",null,l(i.value.user_input||i.value.intent||"未返回"),1)]),e("div",We,[r[12]||(r[12]=e("span",null,"安全决策",-1)),e("strong",null,l(o(V)(i.value.security_decision)),1)]),e("div",Qe,[r[13]||(r[13]=e("span",null,"风险评分",-1)),e("strong",null,l(i.value.risk_score??0)+" / 100 · "+l(o(_e)(i.value.risk_band||i.value.risk_level_text,i.value.risk_score)),1)]),e("div",Xe,[r[14]||(r[14]=e("span",null,"执行状态",-1)),e("strong",null,l(o(j)(i.value)),1)]),e("div",Ye,[r[15]||(r[15]=e("span",null,"工具",-1)),e("strong",null,l(i.value.selected_tool||"未选择工具"),1)])]),e("div",Ze,[r[17]||(r[17]=e("span",null,"规则标签",-1)),k.value.length?w("",!0):(a(),$(o(q),{key:0,size:"small",bordered:!1},{default:u(()=>[...r[16]||(r[16]=[_("无高风险规则",-1)])]),_:1})),(a(!0),v(T,null,P(k.value,t=>(a(),$(o(q),{key:t,size:"small",type:"warning",bordered:!1},{default:u(()=>[_(l(t),1)]),_:2},1024))),128))])],64)):(a(),$(o(E),{key:1,description:"该 request_id 未返回审计摘要"}))]),e("div",er,[r[19]||(r[19]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"Trace 时间线"),e("p",null,"阶段名称来自后端真实审计回放。")])],-1)),c(Ee,{items:x.value.timeline},null,8,["items"])])])):w("",!0),x.value?(a(),v("section",rr,[c(o($e),null,{default:u(()=>[c(o(qe),{title:"高级详情",name:"trace-json"},{default:u(()=>[e("pre",null,l(o(Ce)(x.value)),1)]),_:1})]),_:1})])):w("",!0)],64))}});export{ir as default};
