// 공통: 담당자 정보(?a=직원코드 또는 ?n=&t=&s=) 표시, 전화·문자 버튼, 다음 편 링크에 정보 전달
(function(){
  var DEF = {n:"", c:"", t:"16887038", s:""};
  var q = new URLSearchParams(location.search);
  var keep = new URLSearchParams();
  ["a","n","c","t","s"].forEach(function(k){ if(q.get(k)) keep.set(k, q.get(k)); });
  function fmt(d){
    if(/^(15|16|18)\d{6}$/.test(d)) return d.slice(0,4)+"-"+d.slice(4);
    if(/^02\d{7,8}$/.test(d)) return "02-"+d.slice(2,d.length-4)+"-"+d.slice(-4);
    if(d.length>=10) return d.slice(0,3)+"-"+d.slice(3,d.length-4)+"-"+d.slice(-4);
    return d;
  }
  var IOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
  function apply(d){
    var t = String(d.t||DEF.t).replace(/\D/g,""), s = String(d.s||"").replace(/\D/g,"");
    if(!/^01\d{8,9}$/.test(s)) s = /^01\d{8,9}$/.test(t) ? t : "";
    var name = (d.n||"").slice(0,30), comp = (d.c||"").slice(0,40);
    document.querySelectorAll(".js-name").forEach(function(e){ e.textContent = name || "분양 상담 담당"; });
    document.querySelectorAll(".js-av").forEach(function(e){ e.textContent = name ? name.charAt(0) : "상"; });
    document.querySelectorAll(".js-comp").forEach(function(e){ e.textContent = comp ? " · "+comp : ""; });
    document.querySelectorAll(".js-telno").forEach(function(e){ e.textContent = fmt(t); });
    document.querySelectorAll(".js-tel").forEach(function(a){ a.href = "tel:"+t; });
    document.querySelectorAll(".js-sms").forEach(function(a){
      if(!s){ a.href = "tel:"+t; if(a.dataset.alt) a.textContent = a.dataset.alt; return; }
      var body = "[오산헤리티지자이] " + (a.dataset.body || document.body.dataset.topic || "문의드립니다");
      a.href = "sms:"+s+(IOS?"&":"?")+"body="+encodeURIComponent(body);
    });
    var ks = keep.toString();
    document.querySelectorAll(".js-keep").forEach(function(a){ if(ks) a.href = a.getAttribute("href").split("?")[0] + "?" + ks; });
  }
  var code = q.get("a");
  if(code){
    fetch("../../s/staff.json",{cache:"no-cache"}).then(function(r){return r.json();}).then(function(l){ apply(l[code.toLowerCase()]||{n:q.get("n"),c:q.get("c"),t:q.get("t"),s:q.get("s")}); }).catch(function(){ apply({}); });
  } else apply({n:q.get("n"), c:q.get("c"), t:q.get("t"), s:q.get("s")});
})();
