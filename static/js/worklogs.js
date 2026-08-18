/*
  worklogs.js
  ──────────────────────────────────────────────────────────
  역할: worklogs.html의 날짜 검색 폼을 처리한다.
    - "조회" 버튼(또는 Enter) 클릭 → 폼 기본 제출(페이지 새로고침) 막기
    - 입력된 시작일/종료일을 쿼리 파라미터로 붙여서
      GET /api/worklogs/date?start=...&end=... 호출
    - 결과를 테이블에 그리기

  main.js / errors.js와 다른 점:
    - 페이지가 열리자마자 자동 호출하지 않고, "폼 제출" 이벤트가
      일어났을 때만 fetch를 실행한다. (사용자가 날짜를 직접 고르므로)
*/


// -----------------------------------------------------------------------
// 폼 요소를 가져와서 "submit" 이벤트를 감지한다.
// - <form id="search-form">에 사용자가 버튼을 누르거나 Enter를 치면
//   브라우저 기본 동작은 "페이지를 새로고침하며 폼을 제출"하는 것인데,
//   우리는 그걸 원하지 않는다 (fetch로 비동기 처리할 것이므로).
// - event.preventDefault()로 그 기본 동작을 막는다.
// -----------------------------------------------------------------------
document.getElementById('search-form').addEventListener('submit', function (event) {
  event.preventDefault();   // 페이지 새로고침 방지
  searchWorklogs();
});


/**
 * 입력된 날짜 범위로 워크로그를 조회하는 함수.
 * 폼 제출 시 위 이벤트 리스너에서 호출된다.
 */
function searchWorklogs() {
  const startDate = document.getElementById('start-date').value;   // 예: "2024-01-01"
  const endDate = document.getElementById('end-date').value;
  const statusMessage = document.getElementById('worklog-status-message');

  // 날짜를 둘 다 안 골랐으면 요청 자체를 보내지 않고 사용자에게 안내
  if (!startDate || !endDate) {
    statusMessage.textContent = '시작일과 종료일을 모두 선택해주세요.';
    return;
  }

  statusMessage.textContent = '조회 중...';

  // -----------------------------------------------------------------
  // 쿼리 파라미터 붙이기
  // - worklog.py의 GET /worklogs/date?start=...&end=... 라우트에 맞춰
  //   URL 뒤에 ?start=값&end=값 형태로 붙인다.
  // - encodeURIComponent()로 감싸는 이유:
  //   날짜 형식(YYYY-MM-DD)은 특수문자가 없어서 사실 없어도 되지만,
  //   URL에 값을 넣을 때는 습관적으로 항상 인코딩해주는 게 안전하다.
  //   (한글이나 & 같은 특수문자가 섞여도 깨지지 않게 해줌)
  // -----------------------------------------------------------------
  const url = '/api/worklogs/date?start=' + encodeURIComponent(startDate)
            + '&end=' + encodeURIComponent(endDate);

  fetch(url)
    .then(function (response) {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (data) {
      statusMessage.textContent = startDate + ' ~ ' + endDate + ' 기간 워크로그 ' + data.length + '건';
      renderWorklogTable(data);
    })
    .catch(function (error) {
      console.error('워크로그 조회 실패:', error);
      statusMessage.textContent = '워크로그를 불러오지 못했습니다. (' + error.message + ')';
    });
}


/**
 * 워크로그 배열을 worklog-table-body에 <tr>로 그린다.
 * worklog_service.py에서 duration_minutes(작업시간, 분)가 계산되어 오므로
 * 시작/종료 시각을 직접 빼지 않고 그 값을 그대로 표시한다.
 *
 * @param {Array} worklogs
 */
function renderWorklogTable(worklogs) {
  const tableBody = document.getElementById('worklog-table-body');
  tableBody.innerHTML = '';

  if (worklogs.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="7">해당 기간에 조회된 워크로그가 없습니다.</td></tr>';
    return;
  }

  // 데이터가 많을 수 있으니(기간을 길게 잡으면 수만 건도 가능) 콘솔에 경고만 남긴다.
  // 화면이 느려지면 사용자가 기간을 좁혀서 다시 조회하면 된다.
  if (worklogs.length > 5000) {
    console.warn('워크로그 ' + worklogs.length + '건 — 기간을 좁혀서 조회하는 걸 권장합니다.');
  }

  worklogs.forEach(function (log) {
    const row = document.createElement('tr');

    // worker_type이 'HUMAN'인 작업은 별도 색상으로 구분 (선택적 강조)
    if (log.worker_type === 'HUMAN') {
      row.classList.add('row-human');
    }

    row.innerHTML =
      '<td>' + log.log_id + '</td>' +
      '<td>' + log.robot_id + '</td>' +
      '<td>' + log.work_type + '</td>' +
      '<td>' + log.worker_type + '</td>' +
      '<td>' + log.started_at + '</td>' +
      '<td>' + (log.ended_at || '-') + '</td>' +
      '<td>' + (log.duration_minutes != null ? log.duration_minutes : '-') + '</td>';

    tableBody.appendChild(row);
  });
}

// 페이지가 처음 열렸을 때는 자동 조회하지 않는다.
// (기본 날짜값이 폼에 채워져 있으므로, 사용자가 "조회" 버튼을 눌러야 실행됨 —
//  100만 건 테이블이므로 페이지 열자마자 무조건 쿼리를 날리지 않도록 의도적으로 막음)