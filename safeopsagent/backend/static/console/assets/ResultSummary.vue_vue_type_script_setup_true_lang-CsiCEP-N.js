import{k as a,F as te,R as le,aF as C,aH as n,aK as ne,aJ as E,aI as X,bi as se,bj as ie,d as Q,Y as p,bk as ae,aO as de,aQ as re,aR as ce,v as k,bl as ue,aT as H,c as J,a as y,t as m,f as b,u as r,p as M,q as be,w as i,g as _,h as A,l as pe,o as z,s as K,bm as me,G as ge,I as fe,b9 as he,L as ye,bn as ve}from"./index-DZdajVKh.js";import{u as we,B as Z}from"./PageHeader.vue_vue_type_script_setup_true_lang-CU0Y4O5K.js";import{N as Se,b as xe}from"./CollapseItem-DD9tLhLO.js";import{N as Ce}from"./Alert-C5R1paRp.js";function W(t,g=!0,l=[]){return t.forEach(o=>{if(o!==null){if(typeof o!="object"){(typeof o=="string"||typeof o=="number")&&l.push(a(String(o)));return}if(Array.isArray(o)){W(o,g,l);return}if(o.type===te){if(o.children===null)return;Array.isArray(o.children)&&W(o.children,g,l)}else{if(o.type===le&&g)return;l.push(o)}}}),l}function ze(t,g="default",l=[]){const d=t.$slots[g];return d===void 0?l:d()}function N(t,g="default",l=[]){const{children:o}=t;if(o!==null&&typeof o=="object"&&!Array.isArray(o)){const d=o[g];if(typeof d=="function")return d()}return l}const ke=C([n("descriptions",{fontSize:"var(--n-font-size)"},[n("descriptions-separator",`
 display: inline-block;
 margin: 0 8px 0 2px;
 `),n("descriptions-table-wrapper",[n("descriptions-table",[n("descriptions-table-row",[n("descriptions-table-header",{padding:"var(--n-th-padding)"}),n("descriptions-table-content",{padding:"var(--n-td-padding)"})])])]),ne("bordered",[n("descriptions-table-wrapper",[n("descriptions-table",[n("descriptions-table-row",[C("&:last-child",[n("descriptions-table-content",{paddingBottom:0})])])])])]),E("left-label-placement",[n("descriptions-table-content",[C("> *",{verticalAlign:"top"})])]),E("left-label-align",[C("th",{textAlign:"left"})]),E("center-label-align",[C("th",{textAlign:"center"})]),E("right-label-align",[C("th",{textAlign:"right"})]),E("bordered",[n("descriptions-table-wrapper",`
 border-radius: var(--n-border-radius);
 overflow: hidden;
 background: var(--n-merged-td-color);
 border: 1px solid var(--n-merged-border-color);
 `,[n("descriptions-table",[n("descriptions-table-row",[C("&:not(:last-child)",[n("descriptions-table-content",{borderBottom:"1px solid var(--n-merged-border-color)"}),n("descriptions-table-header",{borderBottom:"1px solid var(--n-merged-border-color)"})]),n("descriptions-table-header",`
 font-weight: 400;
 background-clip: padding-box;
 background-color: var(--n-merged-th-color);
 `,[C("&:not(:last-child)",{borderRight:"1px solid var(--n-merged-border-color)"})]),n("descriptions-table-content",[C("&:not(:last-child)",{borderRight:"1px solid var(--n-merged-border-color)"})])])])])]),n("descriptions-header",`
 font-weight: var(--n-th-font-weight);
 font-size: 18px;
 transition: color .3s var(--n-bezier);
 line-height: var(--n-line-height);
 margin-bottom: 16px;
 color: var(--n-title-text-color);
 `),n("descriptions-table-wrapper",`
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[n("descriptions-table",`
 width: 100%;
 border-collapse: separate;
 border-spacing: 0;
 box-sizing: border-box;
 `,[n("descriptions-table-row",`
 box-sizing: border-box;
 transition: border-color .3s var(--n-bezier);
 `,[n("descriptions-table-header",`
 font-weight: var(--n-th-font-weight);
 line-height: var(--n-line-height);
 display: table-cell;
 box-sizing: border-box;
 color: var(--n-th-text-color);
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),n("descriptions-table-content",`
 vertical-align: top;
 line-height: var(--n-line-height);
 display: table-cell;
 box-sizing: border-box;
 color: var(--n-td-text-color);
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[X("content",`
 transition: color .3s var(--n-bezier);
 display: inline-block;
 color: var(--n-td-text-color);
 `)]),X("label",`
 font-weight: var(--n-th-font-weight);
 transition: color .3s var(--n-bezier);
 display: inline-block;
 margin-right: 14px;
 color: var(--n-th-text-color);
 `)])])])]),n("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color);
 --n-merged-td-color: var(--n-td-color);
 --n-merged-border-color: var(--n-border-color);
 `),se(n("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color-modal);
 --n-merged-td-color: var(--n-td-color-modal);
 --n-merged-border-color: var(--n-border-color-modal);
 `)),ie(n("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color-popover);
 --n-merged-td-color: var(--n-td-color-popover);
 --n-merged-border-color: var(--n-border-color-popover);
 `))]),oe="DESCRIPTION_ITEM_FLAG";function $e(t){return typeof t=="object"&&t&&!Array.isArray(t)?t.type&&t.type[oe]:!1}const Re=Object.assign(Object.assign({},re.props),{title:String,column:{type:Number,default:3},columns:Number,labelPlacement:{type:String,default:"top"},labelAlign:{type:String,default:"left"},separator:{type:String,default:":"},size:String,bordered:Boolean,labelClass:String,labelStyle:[Object,String],contentClass:String,contentStyle:[Object,String]}),ee=Q({name:"Descriptions",props:Re,slots:Object,setup(t){const{mergedClsPrefixRef:g,inlineThemeDisabled:l,mergedComponentPropsRef:o}=de(t),d=k(()=>{var u,c;return t.size||((c=(u=o?.value)===null||u===void 0?void 0:u.Descriptions)===null||c===void 0?void 0:c.size)||"medium"}),h=re("Descriptions","-descriptions",ke,ue,t,g),$=k(()=>{const{bordered:u}=t,c=d.value,{common:{cubicBezierEaseInOut:w},self:{titleTextColor:e,thColor:S,thColorModal:L,thColorPopover:q,thTextColor:V,thFontWeight:Y,tdTextColor:F,tdColor:s,tdColorModal:I,tdColorPopover:G,borderColor:x,borderColorModal:R,borderColorPopover:B,borderRadius:T,lineHeight:P,[H("fontSize",c)]:j,[H(u?"thPaddingBordered":"thPadding",c)]:D,[H(u?"tdPaddingBordered":"tdPadding",c)]:O}}=h.value;return{"--n-title-text-color":e,"--n-th-padding":D,"--n-td-padding":O,"--n-font-size":j,"--n-bezier":w,"--n-th-font-weight":Y,"--n-line-height":P,"--n-th-text-color":V,"--n-td-text-color":F,"--n-th-color":S,"--n-th-color-modal":L,"--n-th-color-popover":q,"--n-td-color":s,"--n-td-color-modal":I,"--n-td-color-popover":G,"--n-border-radius":T,"--n-border-color":x,"--n-border-color-modal":R,"--n-border-color-popover":B}}),v=l?ce("descriptions",k(()=>{let u="";const{bordered:c}=t;return c&&(u+="a"),u+=d.value[0],u}),$,t):void 0;return{mergedClsPrefix:g,cssVars:l?void 0:$,themeClass:v?.themeClass,onRender:v?.onRender,compitableColumn:we(t,["columns","column"]),inlineThemeDisabled:l,mergedSize:d}},render(){const t=this.$slots.default,g=t?W(t()):[];g.length;const{contentClass:l,labelClass:o,compitableColumn:d,labelPlacement:h,labelAlign:$,mergedSize:v,bordered:u,title:c,cssVars:w,mergedClsPrefix:e,separator:S,onRender:L}=this;L?.();const q=g.filter(s=>$e(s)),V={span:0,row:[],secondRow:[],rows:[]},F=q.reduce((s,I,G)=>{const x=I.props||{},R=q.length-1===G,B=["label"in x?x.label:N(I,"label")],T=[N(I)],P=x.span||1,j=s.span;s.span+=P;const D=x.labelStyle||x["label-style"]||this.labelStyle,O=x.contentStyle||x["content-style"]||this.contentStyle;if(h==="left")u?s.row.push(p("th",{class:[`${e}-descriptions-table-header`,o],colspan:1,style:D},B),p("td",{class:[`${e}-descriptions-table-content`,l],colspan:R?(d-j)*2+1:P*2-1,style:O},T)):s.row.push(p("td",{class:`${e}-descriptions-table-content`,colspan:R?(d-j)*2:P*2},p("span",{class:[`${e}-descriptions-table-content__label`,o],style:D},[...B,S&&p("span",{class:`${e}-descriptions-separator`},S)]),p("span",{class:[`${e}-descriptions-table-content__content`,l],style:O},T)));else{const U=R?(d-j)*2:P*2;s.row.push(p("th",{class:[`${e}-descriptions-table-header`,o],colspan:U,style:D},B)),s.secondRow.push(p("td",{class:[`${e}-descriptions-table-content`,l],colspan:U,style:O},T))}return(s.span>=d||R)&&(s.span=0,s.row.length&&(s.rows.push(s.row),s.row=[]),h!=="left"&&s.secondRow.length&&(s.rows.push(s.secondRow),s.secondRow=[])),s},V).rows.map(s=>p("tr",{class:`${e}-descriptions-table-row`},s));return p("div",{style:w,class:[`${e}-descriptions`,this.themeClass,`${e}-descriptions--${h}-label-placement`,`${e}-descriptions--${$}-label-align`,`${e}-descriptions--${v}-size`,u&&`${e}-descriptions--bordered`]},c||this.$slots.header?p("div",{class:`${e}-descriptions-header`},c||ze(this,"header")):null,p("div",{class:`${e}-descriptions-table-wrapper`},p("table",{class:`${e}-descriptions-table`},p("tbody",null,h==="top"&&p("tr",{class:`${e}-descriptions-table-row`,style:{visibility:"collapse"}},ae(d*2,p("td",null))),F))))}}),Pe={label:String,span:{type:Number,default:1},labelClass:String,labelStyle:[Object,String],contentClass:String,contentStyle:[Object,String]},f=Q({name:"DescriptionsItem",[oe]:!0,props:Pe,slots:Object,render(){return null}}),_e={class:"result-summary panel"},Ae={class:"section-heading"},Le={class:"rule-strip"},Ie={key:1,class:"dry-run-panel"},Be={class:"result-actions"},Te={class:"request-id"},qe=Q({__name:"ResultSummary",props:{result:{},confirming:{type:Boolean}},emits:["trace","confirm"],setup(t,{emit:g}){const l=t,o=g,d=k(()=>ye(l.result)),h=k(()=>String(l.result.request_id||l.result.original_request_id||"")),$=k(()=>String(l.result.summary||l.result.response||l.result.error||"后端已返回结果。")),v=k(()=>ve(l.result)),u=k(()=>typeof l.result.confirmation_token=="string"?l.result.confirmation_token:""),c=k(()=>{const w=l.result.dry_run_result;return w&&typeof w=="object"&&!Array.isArray(w)?w:null});return(w,e)=>(z(),J("section",_e,[y("div",Ae,[y("div",null,[e[2]||(e[2]=y("h2",null,"执行结论",-1)),y("p",null,m($.value),1)]),b(r(M),{type:r(be)(t.result.security_decision),bordered:!1},{default:i(()=>[a(m(r(K)(t.result.security_decision)),1)]),_:1},8,["type"])]),v.value?(z(),_(r(Ce),{key:0,class:"environment-note",type:"warning",bordered:!1,title:"环境能力受限"},{default:i(()=>[...e[3]||(e[3]=[a(" 当前环境缺少部分 Linux / 麒麟运维命令，安全链路正常工作，但该工具无法完成真实系统检查。建议在银河麒麟、Linux 或 WSL 环境进行完整演示。 ",-1)])]),_:1})):A("",!0),b(r(ee),{class:"result-facts",bordered:"",column:4,size:"small"},{default:i(()=>[b(r(f),{label:"风险评分"},{default:i(()=>[a(m(t.result.risk_score??0)+" / 100",1)]),_:1}),b(r(f),{label:"风险等级"},{default:i(()=>[a(m(r(me)(t.result.risk_level||t.result.risk_band,t.result.risk_score)),1)]),_:1}),b(r(f),{label:"安全决策"},{default:i(()=>[a(m(r(K)(t.result.security_decision)),1)]),_:1}),b(r(f),{label:"执行状态"},{default:i(()=>[a(m(r(ge)(t.result)),1)]),_:1}),b(r(f),{label:"工具"},{default:i(()=>[a(m(t.result.selected_tool||t.result.tool_name||"未选择工具"),1)]),_:1}),b(r(f),{label:"规划来源"},{default:i(()=>[a(m(r(fe)(t.result.planner_source)),1)]),_:1}),b(r(f),{label:"request_id",span:2},{default:i(()=>[a(m(h.value||"未返回"),1)]),_:1})]),_:1}),y("div",Le,[e[5]||(e[5]=y("span",null,"命中规则",-1)),d.value.length?A("",!0):(z(),_(r(M),{key:0,size:"small",bordered:!1},{default:i(()=>[...e[4]||(e[4]=[a("无高风险规则",-1)])]),_:1})),(z(!0),J(te,null,pe(d.value,S=>(z(),_(r(M),{key:S,size:"small",type:"warning",bordered:!1},{default:i(()=>[a(m(S),1)]),_:2},1024))),128))]),t.result.confirmation_required||u.value?(z(),J("div",Ie,[b(r(M),{type:"warning",bordered:!1},{default:i(()=>[...e[6]||(e[6]=[a("需要人工确认",-1)])]),_:1}),e[9]||(e[9]=y("h3",null,"Dry-run 结果",-1)),e[10]||(e[10]=y("p",null,"该操作需要人工确认，当前尚未执行。确认后仍会再次经过安全校验与审计记录。",-1)),c.value?(z(),_(r(ee),{key:0,class:"dry-run-facts",bordered:"",column:2,size:"small"},{default:i(()=>[b(r(f),{label:"受控工具"},{default:i(()=>[a(m(c.value.tool_name||t.result.tool_name||"未返回"),1)]),_:1}),b(r(f),{label:"风险评分"},{default:i(()=>[a(m(c.value.risk_score??t.result.risk_score??"未返回")+" / 100",1)]),_:1}),b(r(f),{label:"安全决策"},{default:i(()=>[a(m(r(K)(c.value.security_decision||t.result.security_decision)),1)]),_:1}),b(r(f),{label:"当前状态"},{default:i(()=>[...e[7]||(e[7]=[a("尚未执行",-1)])]),_:1}),b(r(f),{label:"说明",span:2},{default:i(()=>[a(m(c.value.message||"该操作需要人工确认，尚未执行。"),1)]),_:1})]),_:1})):A("",!0),u.value?(z(),_(r(Z),{key:1,type:"warning",loading:t.confirming,onClick:e[0]||(e[0]=S=>o("confirm",u.value))},{default:i(()=>[...e[8]||(e[8]=[a("确认执行",-1)])]),_:1},8,["loading"])):A("",!0)])):A("",!0),y("div",Be,[h.value?(z(),_(r(Z),{key:0,secondary:"",type:"primary",onClick:e[1]||(e[1]=S=>o("trace",h.value))},{default:i(()=>[...e[11]||(e[11]=[a("查看安全证据链",-1)])]),_:1})):A("",!0),y("span",Te,m(h.value||"暂无 request_id"),1)]),b(r(Se),{class:"payload-collapse"},{default:i(()=>[b(r(xe),{title:"高级详情",name:"payload"},{default:i(()=>[y("pre",null,m(r(he)(t.result)),1)]),_:1})]),_:1})]))}});export{qe as _,W as f};
