import{d as R,V as o,ah as f,aj as x,ai as n,af as z,bc as H,ak as V,ap as _,r as O,aI as W,ar as T,aq as L,as as q,y as N,bd as K,be as Z,R as G,aN as S,bf as Q,aF as J,bg as X,a4 as k,aG as Y,bh as A,ad as ee,bi as re,bj as ae,Q as te,b2 as le,U as oe}from"./index-DWlCOEFV.js";function D(e,i){let{target:t}=e;for(;t;){if(t.dataset&&t.dataset[i]!==void 0)return!0;t=t.parentElement}return!1}const se=R({name:"ChevronLeft",render(){return o("svg",{viewBox:"0 0 16 16",fill:"none",xmlns:"http://www.w3.org/2000/svg"},o("path",{d:"M10.3536 3.14645C10.5488 3.34171 10.5488 3.65829 10.3536 3.85355L6.20711 8L10.3536 12.1464C10.5488 12.3417 10.5488 12.6583 10.3536 12.8536C10.1583 13.0488 9.84171 13.0488 9.64645 12.8536L5.14645 8.35355C4.95118 8.15829 4.95118 7.84171 5.14645 7.64645L9.64645 3.14645C9.84171 2.95118 10.1583 2.95118 10.3536 3.14645Z",fill:"currentColor"}))}}),ne=R({name:"ChevronRight",render(){return o("svg",{viewBox:"0 0 16 16",fill:"none",xmlns:"http://www.w3.org/2000/svg"},o("path",{d:"M5.64645 3.14645C5.45118 3.34171 5.45118 3.65829 5.64645 3.85355L9.79289 8L5.64645 12.1464C5.45118 12.3417 5.45118 12.6583 5.64645 12.8536C5.84171 13.0488 6.15829 13.0488 6.35355 12.8536L10.8536 8.35355C11.0488 8.15829 11.0488 7.84171 10.8536 7.64645L6.35355 3.14645C6.15829 2.95118 5.84171 2.95118 5.64645 3.14645Z",fill:"currentColor"}))}}),ie=f("collapse","width: 100%;",[f("collapse-item",`
 font-size: var(--n-font-size);
 color: var(--n-text-color);
 transition:
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 margin: var(--n-item-margin);
 `,[x("disabled",[n("header","cursor: not-allowed;",[n("header-main",`
 color: var(--n-title-text-color-disabled);
 `),f("collapse-item-arrow",`
 color: var(--n-arrow-color-disabled);
 `)])]),f("collapse-item","margin-left: 32px;"),z("&:first-child","margin-top: 0;"),z("&:first-child >",[n("header","padding-top: 0;")]),x("left-arrow-placement",[n("header",[f("collapse-item-arrow","margin-right: 4px;")])]),x("right-arrow-placement",[n("header",[f("collapse-item-arrow","margin-left: 4px;")])]),n("content-wrapper",[n("content-inner","padding-top: 16px;"),H({duration:"0.15s"})]),x("active",[n("header",[x("active",[f("collapse-item-arrow","transform: rotate(90deg);")])])]),z("&:not(:first-child)","border-top: 1px solid var(--n-divider-color);"),V("disabled",[x("trigger-area-main",[n("header",[n("header-main","cursor: pointer;"),f("collapse-item-arrow","cursor: default;")])]),x("trigger-area-arrow",[n("header",[f("collapse-item-arrow","cursor: pointer;")])]),x("trigger-area-extra",[n("header",[n("header-extra","cursor: pointer;")])])]),n("header",`
 font-size: var(--n-title-font-size);
 display: flex;
 flex-wrap: nowrap;
 align-items: center;
 transition: color .3s var(--n-bezier);
 position: relative;
 padding: var(--n-title-padding);
 color: var(--n-title-text-color);
 `,[n("header-main",`
 display: flex;
 flex-wrap: nowrap;
 align-items: center;
 font-weight: var(--n-title-font-weight);
 transition: color .3s var(--n-bezier);
 flex: 1;
 color: var(--n-title-text-color);
 `),n("header-extra",`
 display: flex;
 align-items: center;
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 `),f("collapse-item-arrow",`
 display: flex;
 transition:
 transform .15s var(--n-bezier),
 color .3s var(--n-bezier);
 font-size: 18px;
 color: var(--n-arrow-color);
 `)])])]),de=Object.assign(Object.assign({},T.props),{defaultExpandedNames:{type:[Array,String],default:null},expandedNames:[Array,String],arrowPlacement:{type:String,default:"left"},accordion:{type:Boolean,default:!1},displayDirective:{type:String,default:"if"},triggerAreas:{type:Array,default:()=>["main","extra","arrow"]},onItemHeaderClick:[Function,Array],"onUpdate:expandedNames":[Function,Array],onUpdateExpandedNames:[Function,Array],onExpandedNamesChange:{type:[Function,Array],validator:()=>!0,default:void 0}}),F=Z("n-collapse"),fe=R({name:"Collapse",props:de,slots:Object,setup(e,{slots:i}){const{mergedClsPrefixRef:t,inlineThemeDisabled:s,mergedRtlRef:d}=_(e),a=O(e.defaultExpandedNames),h=N(()=>e.expandedNames),v=W(h,a),w=T("Collapse","-collapse",ie,K,e,t);function c(p){const{"onUpdate:expandedNames":l,onUpdateExpandedNames:m,onExpandedNamesChange:y}=e;m&&S(m,p),l&&S(l,p),y&&S(y,p),a.value=p}function g(p){const{onItemHeaderClick:l}=e;l&&S(l,p)}function r(p,l,m){const{accordion:y}=e,{value:I}=v;if(y)p?(c([l]),g({name:l,expanded:!0,event:m})):(c([]),g({name:l,expanded:!1,event:m}));else if(!Array.isArray(I))c([l]),g({name:l,expanded:!0,event:m});else{const C=I.slice(),P=C.findIndex($=>l===$);~P?(C.splice(P,1),c(C),g({name:l,expanded:!1,event:m})):(C.push(l),c(C),g({name:l,expanded:!0,event:m}))}}G(F,{props:e,mergedClsPrefixRef:t,expandedNamesRef:v,slots:i,toggleItem:r});const u=L("Collapse",d,t),E=N(()=>{const{common:{cubicBezierEaseInOut:p},self:{titleFontWeight:l,dividerColor:m,titlePadding:y,titleTextColor:I,titleTextColorDisabled:C,textColor:P,arrowColor:$,fontSize:j,titleFontSize:B,arrowColorDisabled:U,itemMargin:M}}=w.value;return{"--n-font-size":j,"--n-bezier":p,"--n-text-color":P,"--n-divider-color":m,"--n-title-padding":y,"--n-title-font-size":B,"--n-title-text-color":I,"--n-title-text-color-disabled":C,"--n-title-font-weight":l,"--n-arrow-color":$,"--n-arrow-color-disabled":U,"--n-item-margin":M}}),b=s?q("collapse",void 0,E,e):void 0;return{rtlEnabled:u,mergedTheme:w,mergedClsPrefix:t,cssVars:s?void 0:E,themeClass:b?.themeClass,onRender:b?.onRender}},render(){var e;return(e=this.onRender)===null||e===void 0||e.call(this),o("div",{class:[`${this.mergedClsPrefix}-collapse`,this.rtlEnabled&&`${this.mergedClsPrefix}-collapse--rtl`,this.themeClass],style:this.cssVars},this.$slots)}}),ce=R({name:"CollapseItemContent",props:{displayDirective:{type:String,required:!0},show:Boolean,clsPrefix:{type:String,required:!0}},setup(e){return{onceTrue:X(k(e,"show"))}},render(){return o(Q,null,{default:()=>{const{show:e,displayDirective:i,onceTrue:t,clsPrefix:s}=this,d=i==="show"&&t,a=o("div",{class:`${s}-collapse-item__content-wrapper`},o("div",{class:`${s}-collapse-item__content-inner`},this.$slots));return d?J(a,[[Y,e]]):e?a:null}})}}),pe={title:String,name:[String,Number],disabled:Boolean,displayDirective:String},ue=R({name:"CollapseItem",props:pe,setup(e){const{mergedRtlRef:i}=_(e),t=ae(),s=te(()=>{var r;return(r=e.name)!==null&&r!==void 0?r:t}),d=oe(F);d||le("collapse-item","`n-collapse-item` must be placed inside `n-collapse`.");const{expandedNamesRef:a,props:h,mergedClsPrefixRef:v,slots:w}=d,c=N(()=>{const{value:r}=a;if(Array.isArray(r)){const{value:u}=s;return!~r.findIndex(E=>E===u)}else if(r){const{value:u}=s;return u!==r}return!0});return{rtlEnabled:L("Collapse",i,v),collapseSlots:w,randomName:t,mergedClsPrefix:v,collapsed:c,triggerAreas:k(h,"triggerAreas"),mergedDisplayDirective:N(()=>{const{displayDirective:r}=e;return r||h.displayDirective}),arrowPlacement:N(()=>h.arrowPlacement),handleClick(r){let u="main";D(r,"arrow")&&(u="arrow"),D(r,"extra")&&(u="extra"),h.triggerAreas.includes(u)&&d&&!e.disabled&&d.toggleItem(c.value,s.value,r)}}},render(){const{collapseSlots:e,$slots:i,arrowPlacement:t,collapsed:s,mergedDisplayDirective:d,mergedClsPrefix:a,disabled:h,triggerAreas:v}=this,w=A(i.header,{collapsed:s},()=>[this.title]),c=i["header-extra"]||e["header-extra"],g=i.arrow||e.arrow;return o("div",{class:[`${a}-collapse-item`,`${a}-collapse-item--${t}-arrow-placement`,h&&`${a}-collapse-item--disabled`,!s&&`${a}-collapse-item--active`,v.map(r=>`${a}-collapse-item--trigger-area-${r}`)]},o("div",{class:[`${a}-collapse-item__header`,!s&&`${a}-collapse-item__header--active`]},o("div",{class:`${a}-collapse-item__header-main`,onClick:this.handleClick},t==="right"&&w,o("div",{class:`${a}-collapse-item-arrow`,key:this.rtlEnabled?0:1,"data-arrow":!0},A(g,{collapsed:s},()=>[o(ee,{clsPrefix:a},{default:()=>this.rtlEnabled?o(se,null):o(ne,null)})])),t==="left"&&w),re(c,{collapsed:s},r=>o("div",{class:`${a}-collapse-item__header-extra`,onClick:this.handleClick,"data-extra":!0},r))),o(ce,{clsPrefix:a,displayDirective:d,show:!s},i))}});export{fe as N,ue as a,D as h};
