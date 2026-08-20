/*
  worklogs.js
  ──────────────────────────────────────────────────────────
  역할: worklogs.html의 통합 검색 폼을 처리한다.
    - 로봇ID/라인ID/작업유형/작업주체/날짜범위/최소작업시간을
      전부 선택적으로 조합해서 GET /api/worklogs/search 호출
    - 결과를 테이블에 그리고, 페이지네이션 컨트롤(이전/다음)을 갱신

  main.js / errors.js와 다른 점:
    - 페이지가 열리자마자 자동 호출하지 않고, "폼 제출" 이벤트가
      일어났을 때만 fetch를 실행한다. (100만 건 테이블이라 조건 없는
      최초 조회를 의도적으로 막음 — 사용자가 조건을 직접 고르므로)
*/


// -----------------------------------------------------------------------
// 마지막으로 검색에 사용한 필터 조건들을 기억해두는 변수들
// - "이전/다음" 버튼을 눌렀을 때 필터는 그대로 두고 page만 바꿔서
//   다시 조회해야 하므로, 마지막 검색 조건을 여기에 저장해둔다.
// -----------------------------------------------------------------------
let currentFilters = {};
let currentPage = 1;
let currentTotalPages = 1;


document.getElementById('search-form').addEventListener('submit', function (event) {
  event.preventDefault();   // 페이지 새로고침 방지
  currentPage = 1;          // 새로 검색하면 항상 1페이지부터 다시 봄
  searchWorklogs();
});

// "이전" 버튼: 1페이지보다 클 때만 동작
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
 * 폼에 입력된 필터 조건들을 모아서 currentFilters에 저장한다.
 * 조건이 하나도 없으면(=전체 100만 건) 위험하므로 요청 자체를 막는다.
 * 실제 fetch는 fetchWorklogs()가 담당한다.
 */
function searchWorklogs() {
  const statusMessage = document.getElementById('worklog-status-message');

  currentFilters = {
    robot_id: document.getElementById('filter-robot-id').value,
    line_id: document.getElementById('filter-line-id').value,
    work_type: document.getElementById('filter-work-type').value,
    worker_type: document.getElementById('filter-worker-type').value,
    start: document.getElementById('start-date').value,
    end: document.getElementById('end-date').value,
    min_minutes: document.getElementById('filter-min-minutes').value,
  };

  const hasAnyFilter = Object.values(currentFilters).some(function (v) { return v !== ''; });
  if (!hasAnyFilter) {
    statusMessage.textContent = '조건을 하나 이상 선택해주세요.';
    return;
  }

  fetchWorklogs();
}


/**
 * currentFilters / currentPage 기준으로 실제 API를 호출한다.
 * "조회" 버튼과 "이전/다음" 버튼이 공통으로 이 함수를 호출한다
 * (조건은 그대로 두고 페이지만 바뀌는 경우가 있어서 fetch 로직을 따로 뺐다).
 */
function fetchWorklogs() {
  const statusMessage = document.getElementById('worklog-status-message');
  statusMessage.textContent = '조회 중...';

  // -----------------------------------------------------------------
  // URLSearchParams: 값이 있는 항목만 골라서 쿼리 문자열로 조립해준다.
  // - currentFilters를 순회하면서 빈 값('')은 아예 append하지 않음
  //   → 서버 쪽 request.args.get()이 None을 받아서 "조건 없음"으로 처리됨
  // -----------------------------------------------------------------
  const params = new URLSearchParams();
  Object.entries(currentFilters).forEach(function ([key, value]) {
    if (value !== '') params.append(key, value);
  });
  params.append('page', currentPage);

  fetch('/api/worklogs/search?' + params.toString())
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

      statusMessage.textContent = '조건에 맞는 워크로그 총 '
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
    tableBody.innerHTML = '<tr><td colspan="7">조건에 맞는 워크로그가 없습니다.</td></tr>';
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
// (100만 건 테이블이므로 사용자가 조건을 고르고 "조회"를 눌러야 실행됨)