import{aF as s,aH as S,aJ as R,aK as ne,bi as ae,bj as de,d as j,Y as ie,aO as ue,aQ as K,aP as ce,aR as ve,v as N,bo as be,aT as E,c as v,F as T,l as P,g as $,u as o,o as n,a as e,x as pe,h as w,t as l,f as c,w as u,k as _,p as q,r as z,e as me,D as ge,E as he,s as M,bm as fe,G as A,J as _e,i as F,n as H,H as ye,q as I,b9 as ke,L as Ce}from"./index-DZdajVKh.js";import{_ as xe,B}from"./PageHeader.vue_vue_type_script_setup_true_lang-CU0Y4O5K.js";import{N as V}from"./Empty-CVvyg2xm.js";import{N as we}from"./Alert-C5R1paRp.js";import{N as ze}from"./Spin-iG95q66Z.js";import{N as Te}from"./Input-UoIR4l2F.js";import{N as $e,b as qe}from"./CollapseItem-DD9tLhLO.js";import"./fade-in.cssr-fwmgpzzz.js";const Ne=s([S("table",`
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
 `)]),R("bordered",`
 border: 1px solid var(--n-merged-border-color);
 border-radius: var(--n-border-radius);
 `,[s("tr",[s("&:last-child",[s("td",`
 border-bottom: 0 solid var(--n-merged-border-color);
 `)])])]),R("single-line",[s("th",`
 border-right: 0px solid var(--n-merged-border-color);
 `),s("td",`
 border-right: 0px solid var(--n-merged-border-color);
 `)]),R("single-column",[s("tr",[s("&:not(:last-child)",[s("td",`
 border-bottom: 0px solid var(--n-merged-border-color);
 `)])])]),R("striped",[s("tr:nth-of-type(even)",[s("td","background-color: var(--n-td-color-striped)")])]),ne("bottom-bordered",[s("tr",[s("&:last-child",[s("td",`
 border-bottom: 0px solid var(--n-merged-border-color);
 `)])])])]),ae(S("table",`
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
 `)]))]),Re=Object.assign(Object.assign({},K.props),{bordered:{type:Boolean,default:!0},bottomBordered:{type:Boolean,default:!0},singleLine:{type:Boolean,default:!0},striped:Boolean,singleColumn:Boolean,size:String}),Be=j({name:"Table",props:Re,setup(p){const{mergedClsPrefixRef:d,inlineThemeDisabled:g,mergedRtlRef:b,mergedComponentPropsRef:a}=ue(p),m=N(()=>{var y,f;return p.size||((f=(y=a?.value)===null||y===void 0?void 0:y.Table)===null||f===void 0?void 0:f.size)||"medium"}),h=K("Table","-table",Ne,be,p,d),x=ce("Table",b,d),i=N(()=>{const y=m.value,{self:{borderColor:f,tdColor:C,tdColorModal:r,tdColorPopover:t,thColor:L,thColorModal:O,thColorPopover:D,thTextColor:J,tdTextColor:G,borderRadius:Q,thFontWeight:U,lineHeight:W,borderColorModal:Y,borderColorPopover:X,tdColorStriped:Z,tdColorStripedModal:ee,tdColorStripedPopover:re,[E("fontSize",y)]:te,[E("tdPadding",y)]:oe,[E("thPadding",y)]:le},common:{cubicBezierEaseInOut:se}}=h.value;return{"--n-bezier":se,"--n-td-color":C,"--n-td-color-modal":r,"--n-td-color-popover":t,"--n-td-text-color":G,"--n-border-color":f,"--n-border-color-modal":Y,"--n-border-color-popover":X,"--n-border-radius":Q,"--n-font-size":te,"--n-th-color":L,"--n-th-color-modal":O,"--n-th-color-popover":D,"--n-th-font-weight":U,"--n-th-text-color":J,"--n-line-height":W,"--n-td-padding":oe,"--n-th-padding":le,"--n-td-color-striped":Z,"--n-td-color-striped-modal":ee,"--n-td-color-striped-popover":re}}),k=g?ve("table",N(()=>m.value[0]),i,p):void 0;return{rtlEnabled:x,mergedClsPrefix:d,cssVars:g?void 0:i,themeClass:k?.themeClass,onRender:k?.onRender}},render(){var p;const{mergedClsPrefix:d}=this;return(p=this.onRender)===null||p===void 0||p.call(this),ie("table",{class:[`${d}-table`,this.themeClass,{[`${d}-table--rtl`]:this.rtlEnabled,[`${d}-table--bottom-bordered`]:this.bottomBordered,[`${d}-table--bordered`]:this.bordered,[`${d}-table--single-line`]:this.singleLine,[`${d}-table--single-column`]:this.singleColumn,[`${d}-table--striped`]:this.striped}],style:this.cssVars},this.$slots)}}),Pe={key:0,class:"trace-timeline"},Le={class:"trace-rail"},Se={key:0,class:"trace-line"},Ee={class:"trace-content"},Me={class:"trace-title-row"},Ve=j({__name:"TraceTimeline",props:{items:{}},setup(p){function d(g){const b=String(g||"").toLowerCase();return b==="success"||b==="completed"?"success":b==="warning"||b==="skipped"?"warning":b==="error"||b==="failed"||b==="blocked"?"error":"info"}return(g,b)=>p.items?.length?(n(),v("div",Pe,[(n(!0),v(T,null,P(p.items,(a,m)=>(n(),v("div",{key:`${a.title}-${m}`,class:"trace-item"},[e("div",Le,[e("span",{class:pe(["trace-dot",`trace-${d(a.status)}`])},null,2),m<p.items.length-1?(n(),v("span",Se)):w("",!0)]),e("div",Ee,[e("div",Me,[e("strong",null,l(a.title),1),c(o(q),{size:"small",type:d(a.status),bordered:!1},{default:u(()=>[_(l(a.status||"已记录"),1)]),_:2},1032,["type"])]),e("p",null,l(a.description||"该阶段未返回更多说明。"),1)])]))),128))])):(n(),$(o(V),{key:1,description:"暂无可展示的审计时间线"}))}}),je={class:"section-block panel"},Ae={key:0,class:"audit-table-wrap"},Fe={key:1,class:"audit-mobile-list"},He={class:"audit-card-head"},Ie={class:"section-block panel"},Ke={class:"form-actions"},Oe={key:1,class:"section-block grid-2"},De={class:"panel"},Je={class:"data-list"},Ge={class:"data-row"},Qe={class:"data-row"},Ue={class:"data-row"},We={class:"data-row"},Ye={class:"data-row"},Xe={class:"data-row"},Ze={class:"rule-strip"},er={class:"panel"},rr={key:2,class:"section-block panel"},ur=j({__name:"AuditView",setup(p){const d=_e(),g=z(!0),b=z(!1),a=z(""),m=z([]),h=z(String(d.query.request_id||"")),x=z(null),i=N(()=>x.value?.audit||m.value.find(C=>C.request_id===h.value)||null),k=N(()=>i.value?Ce(i.value):[]);async function y(){g.value=!0,a.value="";try{m.value=await F.auditLogs(20)}catch(C){a.value=C instanceof Error?C.message:"审计日志加载失败"}finally{g.value=!1}}async function f(C=h.value){const r=C.trim();if(r){h.value=r,b.value=!0,a.value="";try{x.value=await F.auditTrace(r)}catch(t){a.value=t instanceof Error?t.message:"审计证据链加载失败"}finally{b.value=!1}}}return me(async()=>{await y(),h.value&&await f(h.value)}),(C,r)=>(n(),v(T,null,[c(xe,{eyebrow:"Audit trace",title:"审计追踪",description:"每一次智能运维请求都会生成 request_id，可回放接收请求、风险判断、工具规划、执行状态和审计保存过程。"},{actions:u(()=>[c(o(B),{secondary:"",loading:g.value,onClick:y},{default:u(()=>[...r[3]||(r[3]=[_("刷新日志",-1)])]),_:1},8,["loading"])]),_:1}),a.value?(n(),$(o(we),{key:0,class:"section-block",type:"error",title:"审计数据不可用",bordered:!1},{default:u(()=>[_(l(a.value),1)]),_:1})):w("",!0),e("section",je,[r[7]||(r[7]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"最近操作记录"),e("p",null,"展示真实审计日志，可选择任意 request_id 查看证据链。")])],-1)),c(o(ze),{show:g.value},{default:u(()=>[m.value.length?(n(),v("div",Ae,[c(o(Be),{size:"small",bordered:!1},{default:u(()=>[r[5]||(r[5]=e("thead",null,[e("tr",null,[e("th",null,"时间"),e("th",null,"请求摘要"),e("th",null,"风险"),e("th",null,"安全决策"),e("th",null,"执行状态"),e("th",null,"工具"),e("th",null,"request_id"),e("th",null,"操作")])],-1)),e("tbody",null,[(n(!0),v(T,null,P(m.value,t=>(n(),v("tr",{key:t.request_id},[e("td",null,l(o(H)(t.created_at||t.timestamp)),1),e("td",null,l(t.user_input||t.intent||"受控工具调用"),1),e("td",null,[c(o(q),{size:"small",type:o(ye)(t.risk_score),bordered:!1},{default:u(()=>[_(l(t.risk_score??0)+" / 100",1)]),_:2},1032,["type"])]),e("td",null,[c(o(q),{size:"small",type:o(I)(t.security_decision),bordered:!1},{default:u(()=>[_(l(o(M)(t.security_decision)),1)]),_:2},1032,["type"])]),e("td",null,l(o(A)(t)),1),e("td",null,l(t.selected_tool||"未选择工具"),1),e("td",null,[e("code",null,l(t.request_id),1)]),e("td",null,[c(o(B),{size:"small",text:"",type:"primary",onClick:L=>f(t.request_id)},{default:u(()=>[...r[4]||(r[4]=[_("查看证据链",-1)])]),_:1},8,["onClick"])])]))),128))])]),_:1})])):w("",!0),m.value.length?(n(),v("div",Fe,[(n(!0),v(T,null,P(m.value,t=>(n(),v("article",{key:t.request_id,class:"audit-card"},[e("div",He,[e("strong",null,l(t.user_input||t.intent||"受控工具调用"),1),c(o(q),{size:"small",type:o(I)(t.security_decision),bordered:!1},{default:u(()=>[_(l(o(M)(t.security_decision)),1)]),_:2},1032,["type"])]),e("p",null,l(o(H)(t.created_at||t.timestamp)),1),e("p",null,l(t.request_id),1),c(o(B),{size:"small",secondary:"",type:"primary",onClick:L=>f(t.request_id)},{default:u(()=>[...r[6]||(r[6]=[_("查看证据链",-1)])]),_:1},8,["onClick"])]))),128))])):w("",!0),!m.value.length&&!g.value?(n(),$(o(V),{key:2,description:"暂无审计日志"})):w("",!0)]),_:1},8,["show"])]),e("section",Ie,[r[9]||(r[9]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"证据链查询"),e("p",null,"输入 request_id 后回放单次请求的安全执行链路。")])],-1)),e("div",Ke,[c(o(Te),{value:h.value,"onUpdate:value":r[0]||(r[0]=t=>h.value=t),placeholder:"输入 request_id",onKeydown:r[1]||(r[1]=ge(he(t=>f(),["prevent"]),["enter"]))},null,8,["value"]),c(o(B),{type:"primary",loading:b.value,disabled:!h.value.trim(),onClick:r[2]||(r[2]=t=>f())},{default:u(()=>[...r[8]||(r[8]=[_("查看证据链",-1)])]),_:1},8,["loading","disabled"])])]),x.value?(n(),v("section",Oe,[e("div",De,[r[18]||(r[18]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"审计摘要"),e("p",null,"以人类可读方式展示本次操作的关键结论。")])],-1)),i.value?(n(),v(T,{key:0},[e("div",Je,[e("div",Ge,[r[10]||(r[10]=e("span",null,"request_id",-1)),e("strong",null,l(i.value.request_id||h.value),1)]),e("div",Qe,[r[11]||(r[11]=e("span",null,"请求内容",-1)),e("strong",null,l(i.value.user_input||i.value.intent||"未返回"),1)]),e("div",Ue,[r[12]||(r[12]=e("span",null,"安全决策",-1)),e("strong",null,l(o(M)(i.value.security_decision)),1)]),e("div",We,[r[13]||(r[13]=e("span",null,"风险评分",-1)),e("strong",null,l(i.value.risk_score??0)+" / 100 · "+l(o(fe)(i.value.risk_band||i.value.risk_level_text,i.value.risk_score)),1)]),e("div",Ye,[r[14]||(r[14]=e("span",null,"执行状态",-1)),e("strong",null,l(o(A)(i.value)),1)]),e("div",Xe,[r[15]||(r[15]=e("span",null,"工具",-1)),e("strong",null,l(i.value.selected_tool||"未选择工具"),1)])]),e("div",Ze,[r[17]||(r[17]=e("span",null,"规则标签",-1)),k.value.length?w("",!0):(n(),$(o(q),{key:0,size:"small",bordered:!1},{default:u(()=>[...r[16]||(r[16]=[_("无高风险规则",-1)])]),_:1})),(n(!0),v(T,null,P(k.value,t=>(n(),$(o(q),{key:t,size:"small",type:"warning",bordered:!1},{default:u(()=>[_(l(t),1)]),_:2},1024))),128))])],64)):(n(),$(o(V),{key:1,description:"该 request_id 未返回审计摘要"}))]),e("div",er,[r[19]||(r[19]=e("div",{class:"section-heading"},[e("div",null,[e("h2",null,"Trace 时间线"),e("p",null,"阶段名称来自后端真实审计回放。")])],-1)),c(Ve,{items:x.value.timeline},null,8,["items"])])])):w("",!0),x.value?(n(),v("section",rr,[c(o($e),null,{default:u(()=>[c(o(qe),{title:"高级详情",name:"trace-json"},{default:u(()=>[e("pre",null,l(o(ke)(x.value)),1)]),_:1})]),_:1})])):w("",!0)],64))}});export{ur as default};
