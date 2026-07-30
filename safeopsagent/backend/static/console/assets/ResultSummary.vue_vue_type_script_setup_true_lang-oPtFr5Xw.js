import{ae as C,ag as o,aj as re,ai as O,ah as Q,b3 as oe,b4 as le,d as W,b5 as ne,U as p,b6 as se,ao as ie,aq as ee,ar as ae,aL as de,x as k,b7 as ce,at as G,c as H,a as h,t as m,f as u,u as r,q as V,s as ue,w as n,g as _,h as L,F as be,n as pe,B as X,o as z,k as i,v as K,b8 as me,I as ge,K as fe,aV as ve,O as he,b9 as ye}from"./index--55wUsWM.js";import{N as we,a as Se}from"./CollapseItem-CLoJxwG3.js";import{N as xe}from"./Alert-Bd15w33r.js";function Ce(t,f="default",s=[]){const a=t.$slots[f];return a===void 0?s:a()}function Y(t,f="default",s=[]){const{children:b}=t;if(b!==null&&typeof b=="object"&&!Array.isArray(b)){const a=b[f];if(typeof a=="function")return a()}return s}const ze=C([o("descriptions",{fontSize:"var(--n-font-size)"},[o("descriptions-separator",`
 display: inline-block;
 margin: 0 8px 0 2px;
 `),o("descriptions-table-wrapper",[o("descriptions-table",[o("descriptions-table-row",[o("descriptions-table-header",{padding:"var(--n-th-padding)"}),o("descriptions-table-content",{padding:"var(--n-td-padding)"})])])]),re("bordered",[o("descriptions-table-wrapper",[o("descriptions-table",[o("descriptions-table-row",[C("&:last-child",[o("descriptions-table-content",{paddingBottom:0})])])])])]),O("left-label-placement",[o("descriptions-table-content",[C("> *",{verticalAlign:"top"})])]),O("left-label-align",[C("th",{textAlign:"left"})]),O("center-label-align",[C("th",{textAlign:"center"})]),O("right-label-align",[C("th",{textAlign:"right"})]),O("bordered",[o("descriptions-table-wrapper",`
 border-radius: var(--n-border-radius);
 overflow: hidden;
 background: var(--n-merged-td-color);
 border: 1px solid var(--n-merged-border-color);
 `,[o("descriptions-table",[o("descriptions-table-row",[C("&:not(:last-child)",[o("descriptions-table-content",{borderBottom:"1px solid var(--n-merged-border-color)"}),o("descriptions-table-header",{borderBottom:"1px solid var(--n-merged-border-color)"})]),o("descriptions-table-header",`
 font-weight: 400;
 background-clip: padding-box;
 background-color: var(--n-merged-th-color);
 `,[C("&:not(:last-child)",{borderRight:"1px solid var(--n-merged-border-color)"})]),o("descriptions-table-content",[C("&:not(:last-child)",{borderRight:"1px solid var(--n-merged-border-color)"})])])])])]),o("descriptions-header",`
 font-weight: var(--n-th-font-weight);
 font-size: 18px;
 transition: color .3s var(--n-bezier);
 line-height: var(--n-line-height);
 margin-bottom: 16px;
 color: var(--n-title-text-color);
 `),o("descriptions-table-wrapper",`
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[o("descriptions-table",`
 width: 100%;
 border-collapse: separate;
 border-spacing: 0;
 box-sizing: border-box;
 `,[o("descriptions-table-row",`
 box-sizing: border-box;
 transition: border-color .3s var(--n-bezier);
 `,[o("descriptions-table-header",`
 font-weight: var(--n-th-font-weight);
 line-height: var(--n-line-height);
 display: table-cell;
 box-sizing: border-box;
 color: var(--n-th-text-color);
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),o("descriptions-table-content",`
 vertical-align: top;
 line-height: var(--n-line-height);
 display: table-cell;
 box-sizing: border-box;
 color: var(--n-td-text-color);
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[Q("content",`
 transition: color .3s var(--n-bezier);
 display: inline-block;
 color: var(--n-td-text-color);
 `)]),Q("label",`
 font-weight: var(--n-th-font-weight);
 transition: color .3s var(--n-bezier);
 display: inline-block;
 margin-right: 14px;
 color: var(--n-th-text-color);
 `)])])])]),o("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color);
 --n-merged-td-color: var(--n-td-color);
 --n-merged-border-color: var(--n-border-color);
 `),oe(o("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color-modal);
 --n-merged-td-color: var(--n-td-color-modal);
 --n-merged-border-color: var(--n-border-color-modal);
 `)),le(o("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color-popover);
 --n-merged-td-color: var(--n-td-color-popover);
 --n-merged-border-color: var(--n-border-color-popover);
 `))]),te="DESCRIPTION_ITEM_FLAG";function ke(t){return typeof t=="object"&&t&&!Array.isArray(t)?t.type&&t.type[te]:!1}const $e=Object.assign(Object.assign({},ee.props),{title:String,column:{type:Number,default:3},columns:Number,labelPlacement:{type:String,default:"top"},labelAlign:{type:String,default:"left"},separator:{type:String,default:":"},size:String,bordered:Boolean,labelClass:String,labelStyle:[Object,String],contentClass:String,contentStyle:[Object,String]}),Z=W({name:"Descriptions",props:$e,slots:Object,setup(t){const{mergedClsPrefixRef:f,inlineThemeDisabled:s,mergedComponentPropsRef:b}=ie(t),a=k(()=>{var c,d;return t.size||((d=(c=b?.value)===null||c===void 0?void 0:c.Descriptions)===null||d===void 0?void 0:d.size)||"medium"}),v=ee("Descriptions","-descriptions",ze,ce,t,f),$=k(()=>{const{bordered:c}=t,d=a.value,{common:{cubicBezierEaseInOut:w},self:{titleTextColor:e,thColor:S,thColorModal:A,thColorPopover:q,thTextColor:E,thFontWeight:J,tdTextColor:M,tdColor:l,tdColorModal:B,tdColorPopover:F,borderColor:x,borderColorModal:R,borderColorPopover:I,borderRadius:N,lineHeight:P,[G("fontSize",d)]:T,[G(c?"thPaddingBordered":"thPadding",d)]:j,[G(c?"tdPaddingBordered":"tdPadding",d)]:D}}=v.value;return{"--n-title-text-color":e,"--n-th-padding":j,"--n-td-padding":D,"--n-font-size":T,"--n-bezier":w,"--n-th-font-weight":J,"--n-line-height":P,"--n-th-text-color":E,"--n-td-text-color":M,"--n-th-color":S,"--n-th-color-modal":A,"--n-th-color-popover":q,"--n-td-color":l,"--n-td-color-modal":B,"--n-td-color-popover":F,"--n-border-radius":N,"--n-border-color":x,"--n-border-color-modal":R,"--n-border-color-popover":I}}),y=s?ae("descriptions",k(()=>{let c="";const{bordered:d}=t;return d&&(c+="a"),c+=a.value[0],c}),$,t):void 0;return{mergedClsPrefix:f,cssVars:s?void 0:$,themeClass:y?.themeClass,onRender:y?.onRender,compitableColumn:de(t,["columns","column"]),inlineThemeDisabled:s,mergedSize:a}},render(){const t=this.$slots.default,f=t?ne(t()):[];f.length;const{contentClass:s,labelClass:b,compitableColumn:a,labelPlacement:v,labelAlign:$,mergedSize:y,bordered:c,title:d,cssVars:w,mergedClsPrefix:e,separator:S,onRender:A}=this;A?.();const q=f.filter(l=>ke(l)),E={span:0,row:[],secondRow:[],rows:[]},M=q.reduce((l,B,F)=>{const x=B.props||{},R=q.length-1===F,I=["label"in x?x.label:Y(B,"label")],N=[Y(B)],P=x.span||1,T=l.span;l.span+=P;const j=x.labelStyle||x["label-style"]||this.labelStyle,D=x.contentStyle||x["content-style"]||this.contentStyle;if(v==="left")c?l.row.push(p("th",{class:[`${e}-descriptions-table-header`,b],colspan:1,style:j},I),p("td",{class:[`${e}-descriptions-table-content`,s],colspan:R?(a-T)*2+1:P*2-1,style:D},N)):l.row.push(p("td",{class:`${e}-descriptions-table-content`,colspan:R?(a-T)*2:P*2},p("span",{class:[`${e}-descriptions-table-content__label`,b],style:j},[...I,S&&p("span",{class:`${e}-descriptions-separator`},S)]),p("span",{class:[`${e}-descriptions-table-content__content`,s],style:D},N)));else{const U=R?(a-T)*2:P*2;l.row.push(p("th",{class:[`${e}-descriptions-table-header`,b],colspan:U,style:j},I)),l.secondRow.push(p("td",{class:[`${e}-descriptions-table-content`,s],colspan:U,style:D},N))}return(l.span>=a||R)&&(l.span=0,l.row.length&&(l.rows.push(l.row),l.row=[]),v!=="left"&&l.secondRow.length&&(l.rows.push(l.secondRow),l.secondRow=[])),l},E).rows.map(l=>p("tr",{class:`${e}-descriptions-table-row`},l));return p("div",{style:w,class:[`${e}-descriptions`,this.themeClass,`${e}-descriptions--${v}-label-placement`,`${e}-descriptions--${$}-label-align`,`${e}-descriptions--${y}-size`,c&&`${e}-descriptions--bordered`]},d||this.$slots.header?p("div",{class:`${e}-descriptions-header`},d||Ce(this,"header")):null,p("div",{class:`${e}-descriptions-table-wrapper`},p("table",{class:`${e}-descriptions-table`},p("tbody",null,v==="top"&&p("tr",{class:`${e}-descriptions-table-row`,style:{visibility:"collapse"}},se(a*2,p("td",null))),M))))}}),Re={label:String,span:{type:Number,default:1},labelClass:String,labelStyle:[Object,String],contentClass:String,contentStyle:[Object,String]},g=W({name:"DescriptionsItem",[te]:!0,props:Re,slots:Object,render(){return null}}),Pe={class:"result-summary panel"},_e={class:"section-heading"},Le={class:"rule-strip"},Ae={key:1,class:"dry-run-panel"},Be={class:"result-actions"},Ie={class:"request-id"},De=W({__name:"ResultSummary",props:{result:{},confirming:{type:Boolean}},emits:["trace","confirm"],setup(t,{emit:f}){const s=t,b=f,a=k(()=>he(s.result)),v=k(()=>String(s.result.request_id||s.result.original_request_id||"")),$=k(()=>String(s.result.summary||s.result.response||s.result.error||"后端已返回结果。")),y=k(()=>ye(s.result)),c=k(()=>typeof s.result.confirmation_token=="string"?s.result.confirmation_token:""),d=k(()=>{const w=s.result.dry_run_result;return w&&typeof w=="object"&&!Array.isArray(w)?w:null});return(w,e)=>(z(),H("section",Pe,[h("div",_e,[h("div",null,[e[2]||(e[2]=h("h2",null,"执行结论",-1)),h("p",null,m($.value),1)]),u(r(V),{type:r(ue)(t.result.security_decision),bordered:!1},{default:n(()=>[i(m(r(K)(t.result.security_decision)),1)]),_:1},8,["type"])]),y.value?(z(),_(r(xe),{key:0,class:"environment-note",type:"warning",bordered:!1,title:"环境能力受限"},{default:n(()=>[...e[3]||(e[3]=[i(" 当前环境缺少部分 Linux / 麒麟运维命令，安全链路正常工作，但该工具无法完成真实系统检查。建议在银河麒麟、Linux 或 WSL 环境进行完整演示。 ",-1)])]),_:1})):L("",!0),u(r(Z),{class:"result-facts",bordered:"",column:4,size:"small"},{default:n(()=>[u(r(g),{label:"风险评分"},{default:n(()=>[i(m(t.result.risk_score??0)+" / 100",1)]),_:1}),u(r(g),{label:"风险等级"},{default:n(()=>[i(m(r(me)(t.result.risk_level||t.result.risk_band,t.result.risk_score)),1)]),_:1}),u(r(g),{label:"安全决策"},{default:n(()=>[i(m(r(K)(t.result.security_decision)),1)]),_:1}),u(r(g),{label:"执行状态"},{default:n(()=>[i(m(r(ge)(t.result)),1)]),_:1}),u(r(g),{label:"工具"},{default:n(()=>[i(m(t.result.selected_tool||t.result.tool_name||"未选择工具"),1)]),_:1}),u(r(g),{label:"规划来源"},{default:n(()=>[i(m(r(fe)(t.result.planner_source)),1)]),_:1}),u(r(g),{label:"request_id",span:2},{default:n(()=>[i(m(v.value||"未返回"),1)]),_:1})]),_:1}),h("div",Le,[e[5]||(e[5]=h("span",null,"命中规则",-1)),a.value.length?L("",!0):(z(),_(r(V),{key:0,size:"small",bordered:!1},{default:n(()=>[...e[4]||(e[4]=[i("无高风险规则",-1)])]),_:1})),(z(!0),H(be,null,pe(a.value,S=>(z(),_(r(V),{key:S,size:"small",type:"warning",bordered:!1},{default:n(()=>[i(m(S),1)]),_:2},1024))),128))]),t.result.confirmation_required||c.value?(z(),H("div",Ae,[u(r(V),{type:"warning",bordered:!1},{default:n(()=>[...e[6]||(e[6]=[i("需要人工确认",-1)])]),_:1}),e[9]||(e[9]=h("h3",null,"Dry-run 结果",-1)),e[10]||(e[10]=h("p",null,"该操作需要人工确认，当前尚未执行。确认后仍会再次经过安全校验与审计记录。",-1)),d.value?(z(),_(r(Z),{key:0,class:"dry-run-facts",bordered:"",column:2,size:"small"},{default:n(()=>[u(r(g),{label:"受控工具"},{default:n(()=>[i(m(d.value.tool_name||t.result.tool_name||"未返回"),1)]),_:1}),u(r(g),{label:"风险评分"},{default:n(()=>[i(m(d.value.risk_score??t.result.risk_score??"未返回")+" / 100",1)]),_:1}),u(r(g),{label:"安全决策"},{default:n(()=>[i(m(r(K)(d.value.security_decision||t.result.security_decision)),1)]),_:1}),u(r(g),{label:"当前状态"},{default:n(()=>[...e[7]||(e[7]=[i("尚未执行",-1)])]),_:1}),u(r(g),{label:"说明",span:2},{default:n(()=>[i(m(d.value.message||"该操作需要人工确认，尚未执行。"),1)]),_:1})]),_:1})):L("",!0),c.value?(z(),_(r(X),{key:1,type:"warning",loading:t.confirming,onClick:e[0]||(e[0]=S=>b("confirm",c.value))},{default:n(()=>[...e[8]||(e[8]=[i("确认执行",-1)])]),_:1},8,["loading"])):L("",!0)])):L("",!0),h("div",Be,[v.value?(z(),_(r(X),{key:0,secondary:"",type:"primary",onClick:e[1]||(e[1]=S=>b("trace",v.value))},{default:n(()=>[...e[11]||(e[11]=[i("查看安全证据链",-1)])]),_:1})):L("",!0),h("span",Ie,m(v.value||"暂无 request_id"),1)]),u(r(we),{class:"payload-collapse"},{default:n(()=>[u(r(Se),{title:"高级详情",name:"payload"},{default:n(()=>[h("pre",null,m(r(ve)(t.result)),1)]),_:1})]),_:1})]))}});export{De as _};
