/*
  worklogs.js
  ──────────────────────────────────────────────────────────
  역할: worklogs.html의 날짜 검색 폼을 처리한다.
    - "조회" 버튼(또는 Enter) 클릭 → 폼 기본 제출(페이지 새로고침) 막기
    - 입력된 시작일/종료일을 쿼리 파라미터로 붙여서
      GET /api/worklogs/date?start=...&end=...&page=... 호출
    - 결과를 테이블에 그리고, 페이지네이션 컨트롤(이전/다음)을 갱신

  main.js / errors.js와 다른 점:
    - 페이지가 열리자마자 자동 호출하지 않고, "폼 제출" 이벤트가
      일어났을 때만 fetch를 실행한다. (사용자가 날짜를 직접 고르므로)
*/


// -----------------------------------------------------------------------
// 현재 조회 상태를 기억해두는 변수들
// - "이전/다음" 버튼을 눌렀을 때 날짜는 그대로 두고 page만 바꿔서
//   다시 조회해야 하므로, 마지막으로 검색한 조건을 여기에 저장해둔다.
// -----------------------------------------------------------------------
let currentStartDate = null;
let currentEndDate = null;
let currentPage = 1;
let currentTotalPages = 1;


// -----------------------------------------------------------------------
// 폼 요소를 가져와서 "submit" 이벤트를 감지한다.
// - <form id="search-form">에 사용자가 버튼을 누르거나 Enter를 치면
//   브라우저 기본 동작은 "페이지를 새로고침하며 폼을 제출"하는 것인데,
//   우리는 그걸 원하지 않는다 (fetch로 비동기 처리할 것이므로).
// - event.preventDefault()로 그 기본 동작을 막는다.
// -----------------------------------------------------------------------
document.getElementById('search-form').addEventListener('submit', function (event) {
  event.preventDefault();   // 페이지 새로고침 방지
  currentPage = 1;          // 새로 검색하면 항상 1페이지부터 다시 봄
  searchWorklogs();
});

// "이전" 버튼: 1페이지보다 클 때만 동작 (0페이지나 음수로는 안 감)
document.getElementById('prev-page-btn').addEventListener('click', function () {
  if (currentPage > 1) {
    currentPage -= 1;
    fetchWorklogs();
  }
});

// "다음" 버튼: 마지막 페이지보다 작을 때만 동작
document.getElementById('next-page-btn').addEventListener('click', function () {
  if (currentPage < currentTotalPages) {
    currentPage += 1;
    fetchWorklogs();
  }
});


/**
 * 입력된 날짜 범위로 워크로그를 "처음부터" 조회하는 함수.
 * 폼 제출(조회 버튼) 시 위 이벤트 리스너에서 호출된다.
 * 실제 fetch는 fetchWorklogs()가 담당한다 (날짜/페이지 상태만 여기서 준비).
 */
function searchWorklogs() {
  currentStartDate = document.getElementById('start-date').value;   // 예: "2024-01-01"
  currentEndDate = document.getElementById('end-date').value;

  // 날짜를 둘 다 안 골랐으면 요청 자체를 보내지 않고 사용자에게 안내
  if (!currentStartDate || !currentEndDate) {
    document.getElementById('worklog-status-message').textContent = '시작일과 종료일을 모두 선택해주세요.';
    return;
  }

  fetchWorklogs();
}


/**
 * currentStartDate / currentEndDate / currentPage 기준으로 실제 API를 호출한다.
 * "조회" 버튼과 "이전/다음" 버튼이 공통으로 이 함수를 호출한다
 * (날짜는 그대로 두고 페이지만 바뀌는 경우가 있어서 fetch 로직을 따로 뺐다).
 */
function fetchWorklogs() {
  const statusMessage = document.getElementById('worklog-status-message');
  statusMessage.textContent = '조회 중...';

  // -----------------------------------------------------------------
  // 쿼리 파라미터 붙이기
  // - worklog.py의 GET /worklogs/date?start=...&end=...&page=... 라우트에 맞춰
  //   URL 뒤에 붙인다. per_page는 안 붙이면 서버 기본값(100)이 적용됨.
  // - encodeURIComponent()로 감싸는 이유:
  //   날짜 형식(YYYY-MM-DD)은 특수문자가 없어서 사실 없어도 되지만,
  //   URL에 값을 넣을 때는 습관적으로 항상 인코딩해주는 게 안전하다.
  // -----------------------------------------------------------------
  const url = '/api/worklogs/date?start=' + encodeURIComponent(currentStartDate)
            + '&end=' + encodeURIComponent(currentEndDate)
            + '&page=' + currentPage;

  fetch(url)
    .then(function (response) {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (result) {
      // 응답이 배열이 아니라 {data, page, per_page, total_count, total_pages} 객체로 옴
      currentPage = result.page;
      currentTotalPages = result.total_pages;

      statusMessage.textContent = currentStartDate + ' ~ ' + currentEndDate + ' 기간 워크로그 총 '
        + result.total_count + '건 중 ' + result.data.length + '건 표시';

      renderWorklogTable(result.data);
      updatePaginationControls();
    })
    .catch(function (error) {
      console.error('워크로그 조회 실패:', error);
      statusMessage.textContent = '워크로그를 불러오지 못했습니다. (' + error.message + ')';
    });
}


/**
 * "이전/다음" 버튼과 "N / 전체M 페이지" 표시를 현재 상태에 맞게 갱신한다.
 * - 전체 1페이지뿐이면 컨트롤 자체를 숨김 (버튼 눌러도 할 게 없으므로)
 * - 첫 페이지면 이전 버튼 비활성화, 마지막 페이지면 다음 버튼 비활성화
 */
function updatePaginationControls() {
  const controls = document.getElementById('pagination-controls');
  const indicator = document.getElementById('page-indicator');
  const prevBtn = document.getElementById('prev-page-btn');
  const nextBtn = document.getElementById('next-page-btn');

  if (currentTotalPages <= 1) {
    controls.style.display = 'none';
    return;
  }

  controls.style.display = '';
  indicator.textContent = currentPage + ' / ' + currentTotalPages + ' 페이지';
  prevBtn.disabled = (currentPage <= 1);
  nextBtn.disabled = (currentPage >= currentTotalPages);
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