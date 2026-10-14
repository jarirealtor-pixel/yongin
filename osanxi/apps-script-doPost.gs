// ===== 홈페이지 상담 신청 수신용 (기존 Apps Script 파일 맨 아래에 추가) =====
// 기존 코드의 WEBHOOK_URL 변수를 그대로 사용함
var HOMEPAGE_TAB = '홈페이지_신청';

function doPost(e) {
  var p = (e && e.parameter) || {};
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(HOMEPAGE_TAB);
  if (!sh) {
    sh = ss.insertSheet(HOMEPAGE_TAB);
    sh.appendRow(['접수일시', '이름', '전화번호', '연령대', '관심평형', '유입경로', 'UTM', '상담상태']);
  }
  var phone = String(p.phone || '').replace(/\D/g, '');
  if (!p.name || !/^01\d{8,9}$/.test(phone)) {
    return ContentService.createTextOutput('invalid');
  }
  var now = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm');
  sh.appendRow([now, p.name, "'" + formatPhone(phone), p.age || '', p.size || '', p.ref || '', p.utm || '', '신규']);

  var msg = '🏠 홈페이지 상담 신청! (오산헤리티지자이)\n' +
    '*이름*: ' + p.name + '\n*전화번호*: ' + formatPhone(phone) +
    '\n*연령대*: ' + (p.age || '-') + '\n*관심 평형*: ' + (p.size || '-') +
    '\n*유입*: ' + (p.utm || p.ref || '직접 방문') + '\n*접수*: ' + now;
  UrlFetchApp.fetch(WEBHOOK_URL, {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    payload: JSON.stringify({ text: msg })
  });
  return ContentService.createTextOutput('ok');
}
