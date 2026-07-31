import{d as U,V as o,ad as ne,y as b,aX as se,aY as oe,aZ as ie,a_ as ae,a$ as ge,b0 as L,af as Y,ah as k,aj as T,ap as pe,ar as ue,as as fe,b1 as ve,au as te,c as f,F as P,a as e,f as F,u as q,s as K,w as Z,t as s,h as z,g as V,p as M,o as u,k as J,_ as he}from"./index-DWlCOEFV.js";import{N as X}from"./Empty-9vpgyGAV.js";const me={success:o(ae,null),error:o(ie,null),warning:o(oe,null),info:o(se,null)},ye=U({name:"ProgressCircle",props:{clsPrefix:{type:String,required:!0},status:{type:String,required:!0},strokeWidth:{type:Number,required:!0},fillColor:[String,Object],railColor:String,railStyle:[String,Object],percentage:{type:Number,default:0},offsetDegree:{type:Number,default:0},showIndicator:{type:Boolean,required:!0},indicatorTextColor:String,unit:String,viewBoxWidth:{type:Number,required:!0},gapDegree:{type:Number,required:!0},gapOffsetDegree:{type:Number,default:0}},setup(n,{slots:h}){const $=b(()=>{const p="gradient",{fillColor:l}=n;return typeof l=="object"?`${p}-${ge(JSON.stringify(l))}`:p});function _(p,l,d,w){const{gapDegree:S,viewBoxWidth:g,strokeWidth:C}=n,a=50,m=0,y=a,c=0,I=2*a,D=50+C/2,N=`M ${D},${D} m ${m},${y}
      a ${a},${a} 0 1 1 ${c},${-I}
      a ${a},${a} 0 1 1 ${-c},${I}`,B=Math.PI*2*a,R={stroke:w==="rail"?d:typeof n.fillColor=="object"?`url(#${$.value})`:d,strokeDasharray:`${Math.min(p,100)/100*(B-S)}px ${g*8}px`,strokeDashoffset:`-${S/2}px`,transformOrigin:l?"center":void 0,transform:l?`rotate(${l}deg)`:void 0};return{pathString:N,pathStyle:R}}const v=()=>{const p=typeof n.fillColor=="object",l=p?n.fillColor.stops[0]:"",d=p?n.fillColor.stops[1]:"";return p&&o("defs",null,o("linearGradient",{id:$.value,x1:"0%",y1:"100%",x2:"100%",y2:"0%"},o("stop",{offset:"0%","stop-color":l}),o("stop",{offset:"100%","stop-color":d})))};return()=>{const{fillColor:p,railColor:l,strokeWidth:d,offsetDegree:w,status:S,percentage:g,showIndicator:C,indicatorTextColor:a,unit:m,gapOffsetDegree:y,clsPrefix:c}=n,{pathString:I,pathStyle:D}=_(100,0,l,"rail"),{pathString:N,pathStyle:B}=_(g,w,p,"fill"),R=100+d;return o("div",{class:`${c}-progress-content`,role:"none"},o("div",{class:`${c}-progress-graph`,"aria-hidden":!0},o("div",{class:`${c}-progress-graph-circle`,style:{transform:y?`rotate(${y}deg)`:void 0}},o("svg",{viewBox:`0 0 ${R} ${R}`},v(),o("g",null,o("path",{class:`${c}-progress-graph-circle-rail`,d:I,"stroke-width":d,"stroke-linecap":"round",fill:"none",style:D})),o("g",null,o("path",{class:[`${c}-progress-graph-circle-fill`,g===0&&`${c}-progress-graph-circle-fill--empty`],d:N,"stroke-width":d,"stroke-linecap":"round",fill:"none",style:B}))))),C?o("div",null,h.default?o("div",{class:`${c}-progress-custom-content`,role:"none"},h.default()):S!=="default"?o("div",{class:`${c}-progress-icon`,"aria-hidden":!0},o(ne,{clsPrefix:c},{default:()=>me[S]})):o("div",{class:`${c}-progress-text`,style:{color:a},role:"none"},o("span",{class:`${c}-progress-text__percentage`},g),o("span",{class:`${c}-progress-text__unit`},m))):null)}}}),be={success:o(ae,null),error:o(ie,null),warning:o(oe,null),info:o(se,null)},xe=U({name:"ProgressLine",props:{clsPrefix:{type:String,required:!0},percentage:{type:Number,default:0},railColor:String,railStyle:[String,Object],fillColor:[String,Object],status:{type:String,required:!0},indicatorPlacement:{type:String,required:!0},indicatorTextColor:String,unit:{type:String,default:"%"},processing:{type:Boolean,required:!0},showIndicator:{type:Boolean,required:!0},height:[String,Number],railBorderRadius:[String,Number],fillBorderRadius:[String,Number]},setup(n,{slots:h}){const $=b(()=>L(n.height)),_=b(()=>{var l,d;return typeof n.fillColor=="object"?`linear-gradient(to right, ${(l=n.fillColor)===null||l===void 0?void 0:l.stops[0]} , ${(d=n.fillColor)===null||d===void 0?void 0:d.stops[1]})`:n.fillColor}),v=b(()=>n.railBorderRadius!==void 0?L(n.railBorderRadius):n.height!==void 0?L(n.height,{c:.5}):""),p=b(()=>n.fillBorderRadius!==void 0?L(n.fillBorderRadius):n.railBorderRadius!==void 0?L(n.railBorderRadius):n.height!==void 0?L(n.height,{c:.5}):"");return()=>{const{indicatorPlacement:l,railColor:d,railStyle:w,percentage:S,unit:g,indicatorTextColor:C,status:a,showIndicator:m,processing:y,clsPrefix:c}=n;return o("div",{class:`${c}-progress-content`,role:"none"},o("div",{class:`${c}-progress-graph`,"aria-hidden":!0},o("div",{class:[`${c}-progress-graph-line`,{[`${c}-progress-graph-line--indicator-${l}`]:!0}]},o("div",{class:`${c}-progress-graph-line-rail`,style:[{backgroundColor:d,height:$.value,borderRadius:v.value},w]},o("div",{class:[`${c}-progress-graph-line-fill`,y&&`${c}-progress-graph-line-fill--processing`],style:{maxWidth:`${n.percentage}%`,background:_.value,height:$.value,lineHeight:$.value,borderRadius:p.value}},l==="inside"?o("div",{class:`${c}-progress-graph-line-indicator`,style:{color:C}},h.default?h.default():`${S}${g}`):null)))),m&&l==="outside"?o("div",null,h.default?o("div",{class:`${c}-progress-custom-content`,style:{color:C},role:"none"},h.default()):a==="default"?o("div",{role:"none",class:`${c}-progress-icon ${c}-progress-icon--as-text`,style:{color:C}},S,g):o("div",{class:`${c}-progress-icon`,"aria-hidden":!0},o(ne,{clsPrefix:c},{default:()=>be[a]}))):null)}}});function le(n,h,$=100){return`m ${$/2} ${$/2-n} a ${n} ${n} 0 1 1 0 ${2*n} a ${n} ${n} 0 1 1 0 -${2*n}`}const ke=U({name:"ProgressMultipleCircle",props:{clsPrefix:{type:String,required:!0},viewBoxWidth:{type:Number,required:!0},percentage:{type:Array,default:[0]},strokeWidth:{type:Number,required:!0},circleGap:{type:Number,required:!0},showIndicator:{type:Boolean,required:!0},fillColor:{type:Array,default:()=>[]},railColor:{type:Array,default:()=>[]},railStyle:{type:Array,default:()=>[]}},setup(n,{slots:h}){const $=b(()=>n.percentage.map((p,l)=>`${Math.PI*p/100*(n.viewBoxWidth/2-n.strokeWidth/2*(1+2*l)-n.circleGap*l)*2}, ${n.viewBoxWidth*8}`)),_=(v,p)=>{const l=n.fillColor[p],d=typeof l=="object"?l.stops[0]:"",w=typeof l=="object"?l.stops[1]:"";return typeof n.fillColor[p]=="object"&&o("linearGradient",{id:`gradient-${p}`,x1:"100%",y1:"0%",x2:"0%",y2:"100%"},o("stop",{offset:"0%","stop-color":d}),o("stop",{offset:"100%","stop-color":w}))};return()=>{const{viewBoxWidth:v,strokeWidth:p,circleGap:l,showIndicator:d,fillColor:w,railColor:S,railStyle:g,percentage:C,clsPrefix:a}=n;return o("div",{class:`${a}-progress-content`,role:"none"},o("div",{class:`${a}-progress-graph`,"aria-hidden":!0},o("div",{class:`${a}-progress-graph-circle`},o("svg",{viewBox:`0 0 ${v} ${v}`},o("defs",null,C.map((m,y)=>_(m,y))),C.map((m,y)=>o("g",{key:y},o("path",{class:`${a}-progress-graph-circle-rail`,d:le(v/2-p/2*(1+2*y)-l*y,p,v),"stroke-width":p,"stroke-linecap":"round",fill:"none",style:[{strokeDashoffset:0,stroke:S[y]},g[y]]}),o("path",{class:[`${a}-progress-graph-circle-fill`,m===0&&`${a}-progress-graph-circle-fill--empty`],d:le(v/2-p/2*(1+2*y)-l*y,p,v),"stroke-width":p,"stroke-linecap":"round",fill:"none",style:{strokeDasharray:$.value[y],strokeDashoffset:0,stroke:typeof w[y]=="object"?`url(#gradient-${y})`:w[y]}})))))),d&&h.default?o("div",null,o("div",{class:`${a}-progress-text`},h.default())):null)}}}),we=Y([k("progress",{display:"inline-block"},[k("progress-icon",`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 `),T("line",`
 width: 100%;
 display: block;
 `,[k("progress-content",`
 display: flex;
 align-items: center;
 `,[k("progress-graph",{flex:1})]),k("progress-custom-content",{marginLeft:"14px"}),k("progress-icon",`
 width: 30px;
 padding-left: 14px;
 height: var(--n-icon-size-line);
 line-height: var(--n-icon-size-line);
 font-size: var(--n-icon-size-line);
 `,[T("as-text",`
 color: var(--n-text-color-line-outer);
 text-align: center;
 width: 40px;
 font-size: var(--n-font-size);
 padding-left: 4px;
 transition: color .3s var(--n-bezier);
 `)])]),T("circle, dashboard",{width:"120px"},[k("progress-custom-content",`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 `),k("progress-text",`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 color: inherit;
 font-size: var(--n-font-size-circle);
 color: var(--n-text-color-circle);
 font-weight: var(--n-font-weight-circle);
 transition: color .3s var(--n-bezier);
 white-space: nowrap;
 `),k("progress-icon",`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 color: var(--n-icon-color);
 font-size: var(--n-icon-size-circle);
 `)]),T("multiple-circle",`
 width: 200px;
 color: inherit;
 `,[k("progress-text",`
 font-weight: var(--n-font-weight-circle);
 color: var(--n-text-color-circle);
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 transition: color .3s var(--n-bezier);
 `)]),k("progress-content",{position:"relative"}),k("progress-graph",{position:"relative"},[k("progress-graph-circle",[Y("svg",{verticalAlign:"bottom"}),k("progress-graph-circle-fill",`
 stroke: var(--n-fill-color);
 transition:
 opacity .3s var(--n-bezier),
 stroke .3s var(--n-bezier),
 stroke-dasharray .3s var(--n-bezier);
 `,[T("empty",{opacity:0})]),k("progress-graph-circle-rail",`
 transition: stroke .3s var(--n-bezier);
 overflow: hidden;
 stroke: var(--n-rail-color);
 `)]),k("progress-graph-line",[T("indicator-inside",[k("progress-graph-line-rail",`
 height: 16px;
 line-height: 16px;
 border-radius: 10px;
 `,[k("progress-graph-line-fill",`
 height: inherit;
 border-radius: 10px;
 `),k("progress-graph-line-indicator",`
 background: #0000;
 white-space: nowrap;
 text-align: right;
 margin-left: 14px;
 margin-right: 14px;
 height: inherit;
 font-size: 12px;
 color: var(--n-text-color-line-inner);
 transition: color .3s var(--n-bezier);
 `)])]),T("indicator-inside-label",`
 height: 16px;
 display: flex;
 align-items: center;
 `,[k("progress-graph-line-rail",`
 flex: 1;
 transition: background-color .3s var(--n-bezier);
 `),k("progress-graph-line-indicator",`
 background: var(--n-fill-color);
 font-size: 12px;
 transform: translateZ(0);
 display: flex;
 vertical-align: middle;
 height: 16px;
 line-height: 16px;
 padding: 0 10px;
 border-radius: 10px;
 position: absolute;
 white-space: nowrap;
 color: var(--n-text-color-line-inner);
 transition:
 right .2s var(--n-bezier),
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `)]),k("progress-graph-line-rail",`
 position: relative;
 overflow: hidden;
 height: var(--n-rail-height);
 border-radius: 5px;
 background-color: var(--n-rail-color);
 transition: background-color .3s var(--n-bezier);
 `,[k("progress-graph-line-fill",`
 background: var(--n-fill-color);
 position: relative;
 border-radius: 5px;
 height: inherit;
 width: 100%;
 max-width: 0%;
 transition:
 background-color .3s var(--n-bezier),
 max-width .2s var(--n-bezier);
 `,[T("processing",[Y("&::after",`
 content: "";
 background-image: var(--n-line-bg-processing);
 animation: progress-processing-animation 2s var(--n-bezier) infinite;
 `)])])])])])]),Y("@keyframes progress-processing-animation",`
 0% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 100%;
 opacity: 1;
 }
 66% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 0;
 }
 100% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 0;
 }
 `)]),$e=Object.assign(Object.assign({},ue.props),{processing:Boolean,type:{type:String,default:"line"},gapDegree:Number,gapOffsetDegree:Number,status:{type:String,default:"default"},railColor:[String,Array],railStyle:[String,Array],color:[String,Array,Object],viewBoxWidth:{type:Number,default:100},strokeWidth:{type:Number,default:7},percentage:[Number,Array],unit:{type:String,default:"%"},showIndicator:{type:Boolean,default:!0},indicatorPosition:{type:String,default:"outside"},indicatorPlacement:{type:String,default:"outside"},indicatorTextColor:String,circleGap:{type:Number,default:1},height:Number,borderRadius:[String,Number],fillBorderRadius:[String,Number],offsetDegree:Number}),re=U({name:"Progress",props:$e,setup(n){const h=b(()=>n.indicatorPlacement||n.indicatorPosition),$=b(()=>{if(n.gapDegree||n.gapDegree===0)return n.gapDegree;if(n.type==="dashboard")return 75}),{mergedClsPrefixRef:_,inlineThemeDisabled:v}=pe(n),p=ue("Progress","-progress",we,ve,n,_),l=b(()=>{const{status:w}=n,{common:{cubicBezierEaseInOut:S},self:{fontSize:g,fontSizeCircle:C,railColor:a,railHeight:m,iconSizeCircle:y,iconSizeLine:c,textColorCircle:I,textColorLineInner:D,textColorLineOuter:N,lineBgProcessing:B,fontWeightCircle:R,[te("iconColor",w)]:j,[te("fillColor",w)]:O}}=p.value;return{"--n-bezier":S,"--n-fill-color":O,"--n-font-size":g,"--n-font-size-circle":C,"--n-font-weight-circle":R,"--n-icon-color":j,"--n-icon-size-circle":y,"--n-icon-size-line":c,"--n-line-bg-processing":B,"--n-rail-color":a,"--n-rail-height":m,"--n-text-color-circle":I,"--n-text-color-line-inner":D,"--n-text-color-line-outer":N}}),d=v?fe("progress",b(()=>n.status[0]),l,n):void 0;return{mergedClsPrefix:_,mergedIndicatorPlacement:h,gapDeg:$,cssVars:v?void 0:l,themeClass:d?.themeClass,onRender:d?.onRender}},render(){const{type:n,cssVars:h,indicatorTextColor:$,showIndicator:_,status:v,railColor:p,railStyle:l,color:d,percentage:w,viewBoxWidth:S,strokeWidth:g,mergedIndicatorPlacement:C,unit:a,borderRadius:m,fillBorderRadius:y,height:c,processing:I,circleGap:D,mergedClsPrefix:N,gapDeg:B,gapOffsetDegree:R,themeClass:j,$slots:O,onRender:A}=this;return A?.(),o("div",{class:[j,`${N}-progress`,`${N}-progress--${n}`,`${N}-progress--${v}`],style:h,"aria-valuemax":100,"aria-valuemin":0,"aria-valuenow":w,role:n==="circle"||n==="line"||n==="dashboard"?"progressbar":"none"},n==="circle"||n==="dashboard"?o(ye,{clsPrefix:N,status:v,showIndicator:_,indicatorTextColor:$,railColor:p,fillColor:d,railStyle:l,offsetDegree:this.offsetDegree,percentage:w,viewBoxWidth:S,strokeWidth:g,gapDegree:B===void 0?n==="dashboard"?75:0:B,gapOffsetDegree:R,unit:a},O):n==="line"?o(xe,{clsPrefix:N,status:v,showIndicator:_,indicatorTextColor:$,railColor:p,fillColor:d,railStyle:l,percentage:w,processing:I,indicatorPlacement:C,unit:a,fillBorderRadius:y,railBorderRadius:m,height:c},O):n==="multiple-circle"?o(ke,{clsPrefix:N,strokeWidth:g,railColor:p,fillColor:d,railStyle:l,viewBoxWidth:S,percentage:w,showIndicator:_,circleGap:D},O):null)}}),_e={class:"tool-metrics"},Ce={class:"metric-heading"},Se={class:"metric-grid"},Pe={class:"metric-tile metric-primary"},Ne={class:"metric-tile"},Be={class:"metric-tile"},ze={class:"metric-tile"},Re={class:"metric-tile"},De={class:"metric-tile"},Ie={class:"metric-tile"},We={class:"metric-tile"},qe={class:"metric-heading"},je={class:"metric-grid"},Te={class:"metric-tile metric-primary"},Me={class:"metric-tile"},Oe={class:"metric-tile"},Ae={class:"metric-tile"},Ge={class:"metric-tile"},Le={class:"metric-tile"},Fe={class:"metric-tile"},Ve={key:1,class:"table-scroll"},Xe={key:2,class:"advanced-filesystems"},Ue={class:"table-scroll"},Ye={class:"metric-heading"},Ee={class:"table-scroll"},He=["title"],Ke={class:"table-scroll"},Ze={class:"metric-heading"},Je={key:1,class:"table-scroll"},Qe={class:"fact-list"},et={class:"fact-wide"},tt={class:"log-list"},lt={class:"fact-list compact-facts"},rt={key:1,class:"table-scroll"},nt=["title"],st={class:"metric-heading"},ot={class:"fact-list compact-facts"},it={key:0},at={class:"mono"},ut={key:1},dt={class:"mono"},ct={key:1,class:"table-scroll"},gt=["title"],pt=U({__name:"ToolResultMetrics",props:{toolName:{},data:{},status:{}},setup(n){const h=n;function $(i){return!!i&&typeof i=="object"&&!Array.isArray(i)}function _(i){return Array.isArray(i)?i.filter($):[]}function v(i){if(typeof i=="number"&&Number.isFinite(i))return i;if(typeof i=="string"&&i.trim()){const t=Number(i.replace("%",""));if(Number.isFinite(t))return t}return null}function p(i,t){return i===null||t===null||t<=0?null:Math.round(i/t*1e3)/10}function l(i,t="未返回"){return i==null||i===""?t:String(i)}function d(i){return i===null?"未返回":`${i.toLocaleString()} MB`}function w(i){return i===null?"未返回":`${i.toFixed(1)}%`}function S(i){const t=v(i);if(t===null)return l(i);let r=t;for(const x of["B","KB","MB","GB","TB"]){if(r<1024||x==="TB")return`${r.toFixed(1)} ${x}`;r/=1024}return`${t} B`}const g=b(()=>$(h.data)?h.data:null),C=b(()=>_(h.data)),a=b(()=>{if(h.toolName!=="get_memory_status"||!g.value)return null;const i=v(g.value.total_mb),t=v(g.value.used_mb),r=v(g.value.swap_total_mb),x=v(g.value.swap_used_mb);return{total:i,used:t,free:v(g.value.free_mb),available:v(g.value.available_mb),swapTotal:r,swapUsed:x,memoryPercent:p(t,i),swapPercent:p(x,r)}}),m=b(()=>h.toolName==="get_cpu_status"?g.value:null),y=b(()=>h.toolName==="disk_usage"?C.value:[]),c=new Set(["/","/boot","/boot/efi","/tmp","/home","/var","/var/log"]),I=new Set(["tmpfs","devtmpfs","proc","sysfs","cgroup","cgroup2","efivarfs","securityfs","debugfs","tracefs","pstore","configfs","fusectl","mqueue"]);function D(i){return String(i.mounted_on||i.mount||"")}function N(i){const t=String(i.filesystem||"").toLowerCase(),r=D(i);return c.has(r)?!1:I.has(t)||r==="/dev"||r.startsWith("/dev/")||r==="/proc"||r.startsWith("/proc/")||r==="/sys"||r.startsWith("/sys/")||r==="/run"||r.startsWith("/run/")}const B=b(()=>{const i=y.value.filter(t=>c.has(D(t)));return i.length?i:y.value.filter(t=>!N(t)).slice(0,5)}),R=b(()=>y.value.filter(i=>!B.value.includes(i))),j=b(()=>h.toolName==="process_list"?C.value:h.toolName==="get_cpu_status"?_(g.value?.top_processes):[]),O=b(()=>{if(!m.value)return"success";const i=v(m.value.usage_percent)??0,t=v(m.value.load_per_core)??0,r=j.value.reduce((de,ce)=>Math.max(de,v(ce.cpu)??0),0),x=t>=1||r>=75;return i>=95&&x?"error":i>=85&&x||t>=1?"warning":"success"}),A=b(()=>h.toolName==="network_status"?C.value:[]),Q=b(()=>h.toolName==="get_port_usage"?_(g.value?.listeners):[]),G=b(()=>h.toolName==="get_service_status"?g.value:null),E=b(()=>h.toolName==="journal_query"?C.value:[]),H=b(()=>h.toolName==="large_file_scan"?_(g.value?.files):[]),ee=b(()=>String(h.toolName||"").startsWith("safe_cleanup_")?_(g.value?.candidates||g.value?.items):[]),W=b(()=>String(h.toolName||"").startsWith("safe_cleanup_")?g.value:null);return(i,t)=>(u(),f("section",_e,[a.value?(u(),f(P,{key:0},[e("div",Ce,[t[1]||(t[1]=e("div",null,[e("h3",null,"内存占用"),e("p",null,"来自当前设备的内存与 Swap 数据。")],-1)),F(q(K),{type:"success",bordered:!1},{default:Z(()=>[...t[0]||(t[0]=[J("只读检查",-1)])]),_:1})]),e("div",Se,[e("article",Pe,[t[2]||(t[2]=e("span",null,"内存使用率",-1)),e("strong",null,s(w(a.value.memoryPercent)),1),F(q(re),{type:"line",percentage:a.value.memoryPercent??0,"show-indicator":!1,status:(a.value.memoryPercent??0)>=90?"error":(a.value.memoryPercent??0)>=80?"warning":"success"},null,8,["percentage","status"])]),e("article",Ne,[t[3]||(t[3]=e("span",null,"总内存",-1)),e("strong",null,s(d(a.value.total)),1)]),e("article",Be,[t[4]||(t[4]=e("span",null,"已用内存",-1)),e("strong",null,s(d(a.value.used)),1)]),e("article",ze,[t[5]||(t[5]=e("span",null,"可用内存",-1)),e("strong",null,s(d(a.value.available)),1)]),e("article",Re,[t[6]||(t[6]=e("span",null,"空闲内存",-1)),e("strong",null,s(d(a.value.free)),1)]),e("article",De,[t[7]||(t[7]=e("span",null,"Swap 总量",-1)),e("strong",null,s(d(a.value.swapTotal)),1)]),e("article",Ie,[t[8]||(t[8]=e("span",null,"Swap 已用",-1)),e("strong",null,s(d(a.value.swapUsed)),1)]),e("article",We,[t[9]||(t[9]=e("span",null,"Swap 使用率",-1)),e("strong",null,s(w(a.value.swapPercent)),1)])])],64)):m.value?(u(),f(P,{key:1},[e("div",qe,[e("div",null,[t[10]||(t[10]=e("h3",null,"CPU 与系统负载",-1)),e("p",null," CPU 为 "+s(l(m.value.sample_interval_seconds,"1"))+" 秒瞬时采样， 需结合每核负载与高占用进程判断持续压力。 ",1)]),F(q(K),{type:m.value.status==="environment_limited"?"warning":"success",bordered:!1},{default:Z(()=>[J(s(m.value.status==="environment_limited"?"环境受限":"只读检查"),1)]),_:1},8,["type"])]),e("div",je,[e("article",Te,[t[11]||(t[11]=e("span",null,"CPU 使用率（瞬时采样）",-1)),e("strong",null,s(w(v(m.value.usage_percent))),1),F(q(re),{type:"line",percentage:v(m.value.usage_percent)??0,"show-indicator":!1,status:O.value},null,8,["percentage","status"])]),e("article",Me,[t[12]||(t[12]=e("span",null,"逻辑核心",-1)),e("strong",null,s(l(m.value.logical_cores)),1)]),e("article",Oe,[t[13]||(t[13]=e("span",null,"物理核心",-1)),e("strong",null,s(l(m.value.physical_cores,"无法可靠获取")),1)]),e("article",Ae,[t[14]||(t[14]=e("span",null,"1 分钟负载",-1)),e("strong",null,s(l(m.value.load_1m)),1)]),e("article",Ge,[t[15]||(t[15]=e("span",null,"5 分钟负载",-1)),e("strong",null,s(l(m.value.load_5m)),1)]),e("article",Le,[t[16]||(t[16]=e("span",null,"15 分钟负载",-1)),e("strong",null,s(l(m.value.load_15m)),1)]),e("article",Fe,[t[17]||(t[17]=e("span",null,"每核负载",-1)),e("strong",null,s(l(m.value.load_per_core)),1)])])],64)):z("",!0),y.value.length?(u(),f(P,{key:2},[t[20]||(t[20]=e("div",{class:"metric-heading"},[e("div",null,[e("h3",null,"磁盘空间"),e("p",null,"默认展示关键真实挂载点，虚拟与临时文件系统收纳在高级详情中。")])],-1)),B.value.length?z("",!0):(u(),V(q(X),{key:0,description:"未返回可展示的真实挂载点"})),B.value.length?(u(),f("div",Ve,[e("table",null,[t[18]||(t[18]=e("thead",null,[e("tr",null,[e("th",null,"文件系统"),e("th",null,"挂载点"),e("th",null,"总量"),e("th",null,"已用"),e("th",null,"可用"),e("th",null,"使用率")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(B.value,(r,x)=>(u(),f("tr",{key:x},[e("td",null,s(l(r.filesystem)),1),e("td",null,s(l(r.mounted_on||r.mount)),1),e("td",null,s(l(r.size)),1),e("td",null,s(l(r.used)),1),e("td",null,s(l(r.available||r.avail)),1),e("td",null,s(l(r.use_percent||r.use)),1)]))),128))])])])):z("",!0),R.value.length?(u(),f("details",Xe,[e("summary",null,"高级详情：其他文件系统（"+s(R.value.length)+"）",1),e("div",Ue,[e("table",null,[t[19]||(t[19]=e("thead",null,[e("tr",null,[e("th",null,"文件系统"),e("th",null,"挂载点"),e("th",null,"总量"),e("th",null,"已用"),e("th",null,"可用"),e("th",null,"使用率")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(R.value,(r,x)=>(u(),f("tr",{key:x},[e("td",null,s(l(r.filesystem)),1),e("td",null,s(l(r.mounted_on||r.mount)),1),e("td",null,s(l(r.size)),1),e("td",null,s(l(r.used)),1),e("td",null,s(l(r.available||r.avail)),1),e("td",null,s(l(r.use_percent||r.use)),1)]))),128))])])])])):z("",!0)],64)):z("",!0),j.value.length?(u(),f(P,{key:3},[e("div",Ye,[e("div",null,[e("h3",null,s(n.toolName==="get_cpu_status"?"高 CPU 进程":"运行进程"),1),t[21]||(t[21]=e("p",null,"仅展示后端返回的前十项。",-1))])]),e("div",Ee,[e("table",null,[t[22]||(t[22]=e("thead",null,[e("tr",null,[e("th",null,"PID"),e("th",null,"用户"),e("th",null,"名称"),e("th",null,"CPU"),e("th",null,"内存"),e("th",null,"命令")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(j.value.slice(0,10),(r,x)=>(u(),f("tr",{key:x},[e("td",null,s(l(r.pid)),1),e("td",null,s(l(r.user)),1),e("td",null,s(l(r.name||r.command)),1),e("td",null,s(l(r.cpu))+"%",1),e("td",null,s(l(r.mem))+"%",1),e("td",null,[e("span",{class:"truncate",title:l(r.command)},s(l(r.command)),9,He)])]))),128))])])])],64)):z("",!0),A.value.length?(u(),f(P,{key:4},[t[24]||(t[24]=e("div",{class:"metric-heading"},[e("div",null,[e("h3",null,"网络监听"),e("p",null,"协议、本地地址、状态与关联信息。")])],-1)),e("div",Ke,[e("table",null,[t[23]||(t[23]=e("thead",null,[e("tr",null,[e("th",null,"协议"),e("th",null,"本地地址"),e("th",null,"状态"),e("th",null,"PID / 进程")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(A.value.slice(0,30),(r,x)=>(u(),f("tr",{key:x},[e("td",null,s(l(r.protocol)),1),e("td",null,s(l(r.local_address||r.local)),1),e("td",null,s(l(r.state)),1),e("td",null,s(l(r.process||r.pid)),1)]))),128))])])])],64)):n.toolName==="get_port_usage"&&g.value?(u(),f(P,{key:5},[e("div",Ze,[e("div",null,[t[25]||(t[25]=e("h3",null,"端口占用",-1)),e("p",null,"查询端口 "+s(l(g.value.port))+" 的监听进程。",1)])]),Q.value.length?(u(),f("div",Je,[e("table",null,[t[26]||(t[26]=e("thead",null,[e("tr",null,[e("th",null,"协议"),e("th",null,"监听地址"),e("th",null,"PID"),e("th",null,"进程")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(Q.value,(r,x)=>(u(),f("tr",{key:x},[e("td",null,s(l(r.protocol)),1),e("td",null,s(l(r.local_address)),1),e("td",null,s(l(r.pid)),1),e("td",null,s(l(r.process)),1)]))),128))])])])):(u(),V(q(X),{key:0,description:"未发现监听进程"}))],64)):G.value?(u(),f(P,{key:6},[t[32]||(t[32]=e("div",{class:"metric-heading"},[e("div",null,[e("h3",null,"服务状态"),e("p",null,"systemd 活动状态与只读摘要。")])],-1)),e("div",Qe,[e("div",null,[t[27]||(t[27]=e("span",null,"服务名称",-1)),e("strong",null,s(l(G.value.service_name)),1)]),e("div",null,[t[28]||(t[28]=e("span",null,"活动状态",-1)),e("strong",null,s(l(G.value.active_state)),1)]),e("div",null,[t[29]||(t[29]=e("span",null,"启用状态",-1)),e("strong",null,s(l(G.value.enabled_state)),1)]),e("div",et,[t[31]||(t[31]=e("span",null,"状态摘要",-1)),e("details",null,[t[30]||(t[30]=e("summary",null,"查看摘要",-1)),e("pre",null,s(l(G.value.status_summary||G.value.error)),1)])])])],64)):z("",!0),E.value.length?(u(),f(P,{key:7},[t[33]||(t[33]=e("div",{class:"metric-heading"},[e("div",null,[e("h3",null,"近期系统日志"),e("p",null,"日志内容按安全文本渲染。")])],-1)),e("div",tt,[(u(!0),f(P,null,M(E.value.slice(0,50),(r,x)=>(u(),f("article",{key:x},[e("span",null,s(l(r.timestamp||r.time||r.line,String(x+1))),1),e("strong",null,s(l(r.level||r.source,"日志")),1),e("p",null,s(l(r.content)),1)]))),128))])],64)):z("",!0),n.toolName==="large_file_scan"&&g.value?(u(),f(P,{key:8},[t[38]||(t[38]=e("div",{class:"metric-heading"},[e("div",null,[e("h3",null,"大文件候选"),e("p",null,"只读扫描结果，不代表可以直接删除。")])],-1)),e("div",lt,[e("div",null,[t[34]||(t[34]=e("span",null,"扫描文件",-1)),e("strong",null,s(l(g.value.scanned_files)),1)]),e("div",null,[t[35]||(t[35]=e("span",null,"候选数量",-1)),e("strong",null,s(H.value.length),1)])]),H.value.length?(u(),f("div",rt,[e("table",null,[t[37]||(t[37]=e("thead",null,[e("tr",null,[e("th",null,"路径"),e("th",null,"大小"),e("th",null,"字节数"),e("th",null,"安全提示")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(H.value,(r,x)=>(u(),f("tr",{key:x},[e("td",null,[e("span",{class:"truncate",title:l(r.path)},s(l(r.path)),9,nt)]),e("td",null,s(l(r.size)),1),e("td",null,s(l(r.bytes)),1),t[36]||(t[36]=e("td",null,"先确认归属与备份，不直接删除",-1))]))),128))])])])):(u(),V(q(X),{key:0,description:"未发现达到阈值的大文件"}))],64)):z("",!0),W.value?(u(),f(P,{key:9},[e("div",st,[t[40]||(t[40]=e("div",null,[e("h3",null,"可恢复安全清理"),e("p",null,"扫描和计划不会修改文件；隔离与恢复必须人工确认。")],-1)),F(q(K),{type:"warning",bordered:!1},{default:Z(()=>[...t[39]||(t[39]=[J("永久删除：否",-1)])]),_:1})]),e("div",ot,[e("div",null,[t[41]||(t[41]=e("span",null,"候选文件",-1)),e("strong",null,s(l(W.value.candidate_count??W.value.moved_count??W.value.restored_count,"0")),1)]),e("div",null,[t[42]||(t[42]=e("span",null,"总大小",-1)),e("strong",null,s(S(W.value.total_bytes)),1)]),W.value.plan_id?(u(),f("div",it,[t[43]||(t[43]=e("span",null,"计划编号",-1)),e("strong",at,s(W.value.plan_id),1)])):z("",!0),W.value.quarantine_id?(u(),f("div",ut,[t[44]||(t[44]=e("span",null,"隔离编号",-1)),e("strong",dt,s(W.value.quarantine_id),1)])):z("",!0)]),ee.value.length?(u(),f("div",ct,[e("table",null,[t[45]||(t[45]=e("thead",null,[e("tr",null,[e("th",null,"文件路径"),e("th",null,"大小"),e("th",null,"修改时间"),e("th",null,"状态")])],-1)),e("tbody",null,[(u(!0),f(P,null,M(ee.value,(r,x)=>(u(),f("tr",{key:x},[e("td",null,[e("span",{class:"truncate",title:l(r.path||r.original_path)},s(l(r.path||r.original_path)),9,gt)]),e("td",null,s(S(r.bytes)),1),e("td",null,s(l(r.modified_at||r.modified_at_epoch)),1),e("td",null,s(n.toolName==="safe_cleanup_restore"?"已恢复":n.toolName==="safe_cleanup_quarantine"?"已隔离":"待确认"),1)]))),128))])])])):(u(),V(q(X),{key:0,description:"当前没有可展示的文件项"}))],64)):z("",!0),n.status==="success"&&!a.value&&!m.value&&!y.value.length&&!j.value.length&&!A.value.length&&n.toolName!=="get_port_usage"&&!G.value&&!E.value.length&&n.toolName!=="large_file_scan"&&!W.value?(u(),V(q(X),{key:10,description:"工具已执行，但没有可结构化展示的结果"})):z("",!0)]))}}),ht=he(pt,[["__scopeId","data-v-d4cdf6bd"]]);export{re as N,ht as T};
