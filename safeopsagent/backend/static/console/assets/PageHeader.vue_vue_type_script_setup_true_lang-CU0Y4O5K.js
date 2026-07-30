import{v as $,M as ce,Q as ue,O as be,U as _e,aF as v,aG as Ee,aH as N,d as ee,Y as p,bu as Oe,_ as je,a2 as De,r as H,bH as fe,aJ as x,aI as f,aK as ie,bs as Ne,aL as ae,bE as Ke,aX as Me,bt as Ve,aM as Ge,P as Qe,aO as We,aQ as he,aP as qe,aR as Ae,b1 as Le,b5 as Xe,aT as r,bx as j,bJ as se,c as Y,a as J,t as U,h as le,a8 as Ye,o as Z}from"./index-DZdajVKh.js";function fo(e,a){return $(()=>{for(const c of a)if(e[c]!==void 0)return e[c];return e[a[a.length-1]]})}const K=typeof document<"u"&&typeof window<"u",de=be("n-form-item");function Je(e,{defaultSize:a="medium",mergedSize:c,mergedDisabled:u}={}){const n=ue(de,null);_e(de,null);const M=$(c?()=>c(n):()=>{const{size:g}=e;if(g)return g;if(n){const{mergedSize:T}=n;if(T.value!==void 0)return T.value}return a}),_=$(u?()=>u(n):()=>{const{disabled:g}=e;return g!==void 0?g:n?n.disabled.value:!1}),F=$(()=>{const{status:g}=e;return g||n?.mergedValidationStatus.value});return ce(()=>{n&&n.restoreValidation()}),{mergedSizeRef:M,mergedDisabledRef:_,mergedStatusRef:F,nTriggerFormBlur(){n&&n.handleContentBlur()},nTriggerFormChange(){n&&n.handleContentChange()},nTriggerFormFocus(){n&&n.handleContentFocus()},nTriggerFormInput(){n&&n.handleContentInput()}}}const{cubicBezierEaseInOut:w}=Ee;function Ue({duration:e=".2s",delay:a=".1s"}={}){return[v("&.fade-in-width-expand-transition-leave-from, &.fade-in-width-expand-transition-enter-to",{opacity:1}),v("&.fade-in-width-expand-transition-leave-to, &.fade-in-width-expand-transition-enter-from",`
 opacity: 0!important;
 margin-left: 0!important;
 margin-right: 0!important;
 `),v("&.fade-in-width-expand-transition-leave-active",`
 overflow: hidden;
 transition:
 opacity ${e} ${w},
 max-width ${e} ${w} ${a},
 margin-left ${e} ${w} ${a},
 margin-right ${e} ${w} ${a};
 `),v("&.fade-in-width-expand-transition-enter-active",`
 overflow: hidden;
 transition:
 opacity ${e} ${w} ${a},
 max-width ${e} ${w},
 margin-left ${e} ${w},
 margin-right ${e} ${w};
 `)]}const Ze=N("base-wave",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 border-radius: inherit;
`),eo=ee({name:"BaseWave",props:{clsPrefix:{type:String,required:!0}},setup(e){Oe("-base-wave",Ze,je(e,"clsPrefix"));const a=H(null),c=H(!1);let u=null;return ce(()=>{u!==null&&window.clearTimeout(u)}),{active:c,selfRef:a,play(){u!==null&&(window.clearTimeout(u),c.value=!1,u=null),De(()=>{var n;(n=a.value)===null||n===void 0||n.offsetHeight,c.value=!0,u=window.setTimeout(()=>{c.value=!1,u=null},1e3)})}}},render(){const{clsPrefix:e}=this;return p("div",{ref:"selfRef","aria-hidden":!0,class:[`${e}-base-wave`,this.active&&`${e}-base-wave--active`]})}}),oo=K&&"chrome"in window;K&&navigator.userAgent.includes("Firefox");const ro=K&&navigator.userAgent.includes("Safari")&&!oo;function P(e){return fe(e,[255,255,255,.16])}function D(e){return fe(e,[0,0,0,.12])}const to=be("n-button-group"),no=v([N("button",`
 margin: 0;
 font-weight: var(--n-font-weight);
 line-height: 1;
 font-family: inherit;
 padding: var(--n-padding);
 height: var(--n-height);
 font-size: var(--n-font-size);
 border-radius: var(--n-border-radius);
 color: var(--n-text-color);
 background-color: var(--n-color);
 width: var(--n-width);
 white-space: nowrap;
 outline: none;
 position: relative;
 z-index: auto;
 border: none;
 display: inline-flex;
 flex-wrap: nowrap;
 flex-shrink: 0;
 align-items: center;
 justify-content: center;
 user-select: none;
 -webkit-user-select: none;
 text-align: center;
 cursor: pointer;
 text-decoration: none;
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[x("color",[f("border",{borderColor:"var(--n-border-color)"}),x("disabled",[f("border",{borderColor:"var(--n-border-color-disabled)"})]),ie("disabled",[v("&:focus",[f("state-border",{borderColor:"var(--n-border-color-focus)"})]),v("&:hover",[f("state-border",{borderColor:"var(--n-border-color-hover)"})]),v("&:active",[f("state-border",{borderColor:"var(--n-border-color-pressed)"})]),x("pressed",[f("state-border",{borderColor:"var(--n-border-color-pressed)"})])])]),x("disabled",{backgroundColor:"var(--n-color-disabled)",color:"var(--n-text-color-disabled)"},[f("border",{border:"var(--n-border-disabled)"})]),ie("disabled",[v("&:focus",{backgroundColor:"var(--n-color-focus)",color:"var(--n-text-color-focus)"},[f("state-border",{border:"var(--n-border-focus)"})]),v("&:hover",{backgroundColor:"var(--n-color-hover)",color:"var(--n-text-color-hover)"},[f("state-border",{border:"var(--n-border-hover)"})]),v("&:active",{backgroundColor:"var(--n-color-pressed)",color:"var(--n-text-color-pressed)"},[f("state-border",{border:"var(--n-border-pressed)"})]),x("pressed",{backgroundColor:"var(--n-color-pressed)",color:"var(--n-text-color-pressed)"},[f("state-border",{border:"var(--n-border-pressed)"})])]),x("loading","cursor: wait;"),N("base-wave",`
 pointer-events: none;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 animation-iteration-count: 1;
 animation-duration: var(--n-ripple-duration);
 animation-timing-function: var(--n-bezier-ease-out), var(--n-bezier-ease-out);
 `,[x("active",{zIndex:1,animationName:"button-wave-spread, button-wave-opacity"})]),K&&"MozBoxSizing"in document.createElement("div").style?v("&::moz-focus-inner",{border:0}):null,f("border, state-border",`
 position: absolute;
 left: 0;
 top: 0;
 right: 0;
 bottom: 0;
 border-radius: inherit;
 transition: border-color .3s var(--n-bezier);
 pointer-events: none;
 `),f("border",`
 border: var(--n-border);
 `),f("state-border",`
 border: var(--n-border);
 border-color: #0000;
 z-index: 1;
 `),f("icon",`
 margin: var(--n-icon-margin);
 margin-left: 0;
 height: var(--n-icon-size);
 width: var(--n-icon-size);
 max-width: var(--n-icon-size);
 font-size: var(--n-icon-size);
 position: relative;
 flex-shrink: 0;
 `,[N("icon-slot",`
 height: var(--n-icon-size);
 width: var(--n-icon-size);
 position: absolute;
 left: 0;
 top: 50%;
 transform: translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 `,[Ne({top:"50%",originalTransform:"translateY(-50%)"})]),Ue()]),f("content",`
 display: flex;
 align-items: center;
 flex-wrap: nowrap;
 min-width: 0;
 `,[v("~",[f("icon",{margin:"var(--n-icon-margin)",marginRight:0})])]),x("block",`
 display: flex;
 width: 100%;
 `),x("dashed",[f("border, state-border",{borderStyle:"dashed !important"})]),x("disabled",{cursor:"not-allowed",opacity:"var(--n-opacity-disabled)"})]),v("@keyframes button-wave-spread",{from:{boxShadow:"0 0 0.5px 0 var(--n-ripple-color)"},to:{boxShadow:"0 0 0.5px 4.5px var(--n-ripple-color)"}}),v("@keyframes button-wave-opacity",{from:{opacity:"var(--n-wave-opacity)"},to:{opacity:0}})]),io=Object.assign(Object.assign({},he.props),{color:String,textColor:String,text:Boolean,block:Boolean,loading:Boolean,disabled:Boolean,circle:Boolean,size:String,ghost:Boolean,round:Boolean,secondary:Boolean,tertiary:Boolean,quaternary:Boolean,strong:Boolean,focusable:{type:Boolean,default:!0},keyboard:{type:Boolean,default:!0},tag:{type:String,default:"button"},type:{type:String,default:"default"},dashed:Boolean,renderIcon:Function,iconPlacement:{type:String,default:"left"},attrType:{type:String,default:"button"},bordered:{type:Boolean,default:!0},onClick:[Function,Array],nativeFocusBehavior:{type:Boolean,default:!ro},spinProps:Object}),ao=ee({name:"Button",props:io,slots:Object,setup(e){const a=H(null),c=H(null),u=H(!1),n=Qe(()=>!e.quaternary&&!e.tertiary&&!e.secondary&&!e.text&&(!e.color||e.ghost||e.dashed)&&e.bordered),M=ue(to,{}),{inlineThemeDisabled:_,mergedClsPrefixRef:F,mergedRtlRef:g,mergedComponentPropsRef:T}=We(e),{mergedSizeRef:V}=Je({},{defaultSize:"medium",mergedSize:t=>{var b,m;const{size:o}=e;if(o)return o;const{size:R}=M;if(R)return R;const{mergedSize:z}=t||{};if(z)return z.value;const I=(m=(b=T?.value)===null||b===void 0?void 0:b.Button)===null||m===void 0?void 0:m.size;return I||"medium"}}),G=$(()=>e.focusable&&!e.disabled),ve=t=>{var b;G.value||t.preventDefault(),!e.nativeFocusBehavior&&(t.preventDefault(),!e.disabled&&G.value&&((b=a.value)===null||b===void 0||b.focus({preventScroll:!0})))},pe=t=>{var b;if(!e.disabled&&!e.loading){const{onClick:m}=e;m&&Le(m,t),e.text||(b=c.value)===null||b===void 0||b.play()}},ge=t=>{switch(t.key){case"Enter":if(!e.keyboard)return;u.value=!1}},me=t=>{switch(t.key){case"Enter":if(!e.keyboard||e.loading){t.preventDefault();return}u.value=!0}},ye=()=>{u.value=!1},xe=he("Button","-button",no,Xe,e,F),Ce=qe("Button",g,F),oe=$(()=>{const t=xe.value,{common:{cubicBezierEaseInOut:b,cubicBezierEaseOut:m},self:o}=t,{rippleDuration:R,opacityDisabled:z,fontWeight:I,fontWeightStrong:Q}=o,y=V.value,{dashed:W,type:S,ghost:q,text:C,color:s,round:re,circle:A,textColor:B,secondary:we,tertiary:te,quaternary:$e,strong:ze}=e,Se={"--n-font-weight":ze?Q:I};let l={"--n-color":"initial","--n-color-hover":"initial","--n-color-pressed":"initial","--n-color-focus":"initial","--n-color-disabled":"initial","--n-ripple-color":"initial","--n-text-color":"initial","--n-text-color-hover":"initial","--n-text-color-pressed":"initial","--n-text-color-focus":"initial","--n-text-color-disabled":"initial"};const E=S==="tertiary",ne=S==="default",i=E?"default":S;if(C){const d=B||s;l={"--n-color":"#0000","--n-color-hover":"#0000","--n-color-pressed":"#0000","--n-color-focus":"#0000","--n-color-disabled":"#0000","--n-ripple-color":"#0000","--n-text-color":d||o[r("textColorText",i)],"--n-text-color-hover":d?P(d):o[r("textColorTextHover",i)],"--n-text-color-pressed":d?D(d):o[r("textColorTextPressed",i)],"--n-text-color-focus":d?P(d):o[r("textColorTextHover",i)],"--n-text-color-disabled":d||o[r("textColorTextDisabled",i)]}}else if(q||W){const d=B||s;l={"--n-color":"#0000","--n-color-hover":"#0000","--n-color-pressed":"#0000","--n-color-focus":"#0000","--n-color-disabled":"#0000","--n-ripple-color":s||o[r("rippleColor",i)],"--n-text-color":d||o[r("textColorGhost",i)],"--n-text-color-hover":d?P(d):o[r("textColorGhostHover",i)],"--n-text-color-pressed":d?D(d):o[r("textColorGhostPressed",i)],"--n-text-color-focus":d?P(d):o[r("textColorGhostHover",i)],"--n-text-color-disabled":d||o[r("textColorGhostDisabled",i)]}}else if(we){const d=ne?o.textColor:E?o.textColorTertiary:o[r("color",i)],h=s||d,O=S!=="default"&&S!=="tertiary";l={"--n-color":O?j(h,{alpha:Number(o.colorOpacitySecondary)}):o.colorSecondary,"--n-color-hover":O?j(h,{alpha:Number(o.colorOpacitySecondaryHover)}):o.colorSecondaryHover,"--n-color-pressed":O?j(h,{alpha:Number(o.colorOpacitySecondaryPressed)}):o.colorSecondaryPressed,"--n-color-focus":O?j(h,{alpha:Number(o.colorOpacitySecondaryHover)}):o.colorSecondaryHover,"--n-color-disabled":o.colorSecondary,"--n-ripple-color":"#0000","--n-text-color":h,"--n-text-color-hover":h,"--n-text-color-pressed":h,"--n-text-color-focus":h,"--n-text-color-disabled":h}}else if(te||$e){const d=ne?o.textColor:E?o.textColorTertiary:o[r("color",i)],h=s||d;te?(l["--n-color"]=o.colorTertiary,l["--n-color-hover"]=o.colorTertiaryHover,l["--n-color-pressed"]=o.colorTertiaryPressed,l["--n-color-focus"]=o.colorSecondaryHover,l["--n-color-disabled"]=o.colorTertiary):(l["--n-color"]=o.colorQuaternary,l["--n-color-hover"]=o.colorQuaternaryHover,l["--n-color-pressed"]=o.colorQuaternaryPressed,l["--n-color-focus"]=o.colorQuaternaryHover,l["--n-color-disabled"]=o.colorQuaternary),l["--n-ripple-color"]="#0000",l["--n-text-color"]=h,l["--n-text-color-hover"]=h,l["--n-text-color-pressed"]=h,l["--n-text-color-focus"]=h,l["--n-text-color-disabled"]=h}else l={"--n-color":s||o[r("color",i)],"--n-color-hover":s?P(s):o[r("colorHover",i)],"--n-color-pressed":s?D(s):o[r("colorPressed",i)],"--n-color-focus":s?P(s):o[r("colorFocus",i)],"--n-color-disabled":s||o[r("colorDisabled",i)],"--n-ripple-color":s||o[r("rippleColor",i)],"--n-text-color":B||(s?o.textColorPrimary:E?o.textColorTertiary:o[r("textColor",i)]),"--n-text-color-hover":B||(s?o.textColorHoverPrimary:o[r("textColorHover",i)]),"--n-text-color-pressed":B||(s?o.textColorPressedPrimary:o[r("textColorPressed",i)]),"--n-text-color-focus":B||(s?o.textColorFocusPrimary:o[r("textColorFocus",i)]),"--n-text-color-disabled":B||(s?o.textColorDisabledPrimary:o[r("textColorDisabled",i)])};let L={"--n-border":"initial","--n-border-hover":"initial","--n-border-pressed":"initial","--n-border-focus":"initial","--n-border-disabled":"initial"};C?L={"--n-border":"none","--n-border-hover":"none","--n-border-pressed":"none","--n-border-focus":"none","--n-border-disabled":"none"}:L={"--n-border":o[r("border",i)],"--n-border-hover":o[r("borderHover",i)],"--n-border-pressed":o[r("borderPressed",i)],"--n-border-focus":o[r("borderFocus",i)],"--n-border-disabled":o[r("borderDisabled",i)]};const{[r("height",y)]:X,[r("fontSize",y)]:Be,[r("padding",y)]:Pe,[r("paddingRound",y)]:Te,[r("iconSize",y)]:ke,[r("borderRadius",y)]:Re,[r("iconMargin",y)]:Ie,waveOpacity:Fe}=o,He={"--n-width":A&&!C?X:"initial","--n-height":C?"initial":X,"--n-font-size":Be,"--n-padding":A||C?"initial":re?Te:Pe,"--n-icon-size":ke,"--n-icon-margin":Ie,"--n-border-radius":C?"initial":A||re?X:Re};return Object.assign(Object.assign(Object.assign(Object.assign({"--n-bezier":b,"--n-bezier-ease-out":m,"--n-ripple-duration":R,"--n-opacity-disabled":z,"--n-wave-opacity":Fe},Se),l),L),He)}),k=_?Ae("button",$(()=>{let t="";const{dashed:b,type:m,ghost:o,text:R,color:z,round:I,circle:Q,textColor:y,secondary:W,tertiary:S,quaternary:q,strong:C}=e;b&&(t+="a"),o&&(t+="b"),R&&(t+="c"),I&&(t+="d"),Q&&(t+="e"),W&&(t+="f"),S&&(t+="g"),q&&(t+="h"),C&&(t+="i"),z&&(t+=`j${se(z)}`),y&&(t+=`k${se(y)}`);const{value:s}=V;return t+=`l${s[0]}`,t+=`m${m[0]}`,t}),oe,e):void 0;return{selfElRef:a,waveElRef:c,mergedClsPrefix:F,mergedFocusable:G,mergedSize:V,showBorder:n,enterPressed:u,rtlEnabled:Ce,handleMousedown:ve,handleKeydown:me,handleBlur:ye,handleKeyup:ge,handleClick:pe,customColorCssVars:$(()=>{const{color:t}=e;if(!t)return null;const b=P(t);return{"--n-border-color":t,"--n-border-color-hover":b,"--n-border-color-pressed":D(t),"--n-border-color-focus":b,"--n-border-color-disabled":t}}),cssVars:_?void 0:oe,themeClass:k?.themeClass,onRender:k?.onRender}},render(){const{mergedClsPrefix:e,tag:a,onRender:c}=this;c?.();const u=ae(this.$slots.default,n=>n&&p("span",{class:`${e}-button__content`},n));return p(a,{ref:"selfElRef",class:[this.themeClass,`${e}-button`,`${e}-button--${this.type}-type`,`${e}-button--${this.mergedSize}-type`,this.rtlEnabled&&`${e}-button--rtl`,this.disabled&&`${e}-button--disabled`,this.block&&`${e}-button--block`,this.enterPressed&&`${e}-button--pressed`,!this.text&&this.dashed&&`${e}-button--dashed`,this.color&&`${e}-button--color`,this.secondary&&`${e}-button--secondary`,this.loading&&`${e}-button--loading`,this.ghost&&`${e}-button--ghost`],tabindex:this.mergedFocusable?0:-1,type:this.attrType,style:this.cssVars,disabled:this.disabled,onClick:this.handleClick,onBlur:this.handleBlur,onMousedown:this.handleMousedown,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},this.iconPlacement==="right"&&u,p(Ke,{width:!0},{default:()=>ae(this.$slots.icon,n=>(this.loading||this.renderIcon||n)&&p("span",{class:`${e}-button__icon`,style:{margin:Me(this.$slots.default)?"0":""}},p(Ve,null,{default:()=>this.loading?p(Ge,Object.assign({clsPrefix:e,key:"loading",class:`${e}-icon-slot`,strokeWidth:20},this.spinProps)):p("div",{key:"icon",class:`${e}-icon-slot`,role:"none"},this.renderIcon?this.renderIcon():n)})))}),this.iconPlacement==="left"&&u,this.text?null:p(eo,{ref:"waveElRef",clsPrefix:e}),this.showBorder?p("div",{"aria-hidden":!0,class:`${e}-button__border`,style:this.customColorCssVars}):null,this.showBorder?p("div",{"aria-hidden":!0,class:`${e}-button__state-border`,style:this.customColorCssVars}):null)}}),ho=ao,so={class:"page-header"},lo={key:0,class:"eyebrow"},co={class:"page-description"},uo={key:0,class:"page-actions"},vo=ee({__name:"PageHeader",props:{eyebrow:{},title:{},description:{}},setup(e){return(a,c)=>(Z(),Y("header",so,[J("div",null,[e.eyebrow?(Z(),Y("p",lo,U(e.eyebrow),1)):le("",!0),J("h1",null,U(e.title),1),J("p",co,U(e.description),1)]),a.$slots.actions?(Z(),Y("div",uo,[Ye(a.$slots,"actions")])):le("",!0)]))}});export{ao as B,ho as X,vo as _,Je as a,ro as i,fo as u};
