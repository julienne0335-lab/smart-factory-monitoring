/*
  errors.js
  ──────────────────────────────────────────────────────────
  역할: errors.html 안의 세 섹션을 채운다. (10단계 후 순서 재배치:
  "지금 급한 것"(미처리 검색) 먼저, "누적 참고용 통계"는 맨 아래로)
    1. 로봇 에러 통합검색   → GET /api/errors/robot/search        (필터+페이지네이션)
    2. 라인 에러 검색       → GET /api/errors/line/search         (필터+페이지네이션)
    3. 로봇별 누적 에러 통계 → GET /api/errors/stats/robot        (필터 없음, 참고용)

  섹션 1/2는 main.js(/api/robots/search) · worklogs.js(/api/worklogs/search)와
  완전히 동일한 패턴을 쓴다:
    currentFilters(상태 기억) → fetchX()가 API 호출 → 응답의
    {data, page, per_page, total_count, total_pages}를 표 + 페이지네이션에 반영.
  섹션이 2개로 늘었을 뿐이라, 변수/함수 이름 앞에 각각 robotError / lineError
  접두어를 붙여서 서로 상태가 섞이지 않게 분리했다.
*/


// =============================================================
// 섹션 1. 로봇 에러 통합검색
// =============================================================

let robotErrorFilters = {};
let robotErrorPage = 1;
let robotErrorTotalPages = 1;

document.getElementById('robot-error-search-form').addEventListener('submit', function (event) {
  event.preventDefault();   // 페이지 새로고침 방지
  robotErrorPage = 1;       // 새로 검색하면 항상 1페이지부터
  searchRobotErrors();
});

document.getElementById('robot-error-prev-btn').addEventListener('click', function () {
  if (robotErrorPage > 1) {
    robotErrorPage -= 1;
    fetchRobotErrors();
  }
});

document.getElementById('robot-error-next-btn').addEventListener('click', function () {
  if (robotErrorPage < robotErrorTotalPages) {
    robotErrorPage += 1;
    fetchRobotErrors();
  }
});


/**
 * 폼에 입력된 필터 조건들을 모아서 robotErrorFilters에 저장하고 조회를 시작한다.
 * RobotError는 500건뿐이라 조건이 하나도 없어도(=전체 조회) 막지 않는다.
 */
function searchRobotErrors() {
  robotErrorFilters = {
    robot_id: document.getElementById('re-filter-robot-id').value,
    line_id: document.getElementById('re-filter-line-id').value,
    error_type: document.getElementById('re-filter-error-type').value,
    status: document.getElementById('re-filter-status').value,
    start: document.getElementById('re-start-date').value,
    end: document.getElementById('re-end-date').value,
  };
  fetchRobotErrors();
}


/**
 * robotErrorFilters / robotErrorPage 기준으로 실제 API를 호출한다.
 * "검색" 버튼과 "이전/다음" 버튼이 공통으로 이 함수를 호출한다.
 */
function fetchRobotErrors() {
  const statusMessage = document.getElementById('robot-error-status-message');
  statusMessage.textContent = '로봇 에러를 불러오는 중...';

  const params = new URLSearchParams();
  Object.entries(robotErrorFilters).forEach(function ([key, value]) {
    if (value !== '') params.append(key, value);
  });
  params.append('page', robotErrorPage);

  fetch('/api/errors/robot/search?' + params.toString())
    .then(function (response) {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (result) {
      robotErrorPage = result.page;
      robotErrorTotalPages = result.total_pages;

      statusMessage.textContent = '조건에 맞는 로봇 에러 총 ' + result.total_count
        + '건 중 ' + result.data.length + '건 표시 (마지막 갱신: '
        + new Date().toLocaleTimeString() + ')';

      renderRobotErrorTable(result.data);
      updateRobotErrorPaginationControls();
    })
    .catch(function (error) {
      console.error('로봇 에러 조회 실패:', error);
      statusMessage.textContent = '로봇 에러를 불러오지 못했습니다. (' + error.message + ')';
    });
}


/**
 * "이전/다음" 버튼과 "N / 전체M 페이지" 표시를 현재 상태에 맞게 갱신한다.
 */
function updateRobotErrorPaginationControls() {
  const controls = document.getElementById('robot-error-pagination-controls');
  const indicator = document.getElementById('robot-error-page-indicator');
  const prevBtn = document.getElementById('robot-error-prev-btn');
  const nextBtn = document.getElementById('robot-error-next-btn');

  if (robotErrorTotalPages <= 1) {
    controls.style.display = 'none';
    return;
  }

  controls.style.display = '';
  indicator.textContent = robotErrorPage + ' / ' + robotErrorTotalPages + ' 페이지';
  prevBtn.disabled = (robotErrorPage <= 1);
  nextBtn.disabled = (robotErrorPage >= robotErrorTotalPages);
}


/**
 * 로봇 에러 배열을 robot-error-table-body에 <tr>로 그린다.
 * is_pending은 service 계층에서 계산되어 옴 (status === '미처리').
 */
function renderRobotErrorTable(errors) {
  const tableBody = document.getElementById('robot-error-table-body');
  tableBody.innerHTML = '';

  if (errors.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="5">조건에 맞는 로봇 에러가 없습니다.</td></tr>';
    return;
  }

  errors.forEach(function (error) {
    const row = document.createElement('tr');
    if (error.is_pending) row.classList.add('row-alert');

    row.innerHTML =
      '<td>' + error.error_id + '</td>' +
      '<td>' + error.robot_id + '</td>' +
      '<td>' + error.error_type + '</td>' +
      '<td>' + error.status + '</td>' +
      '<td>' + error.occurred_at + '</td>';

    tableBody.appendChild(row);
  });
}


// =============================================================
// 섹션 2. 라인 에러 검색
// =============================================================

let lineErrorFilters = {};
let lineErrorPage = 1;
let lineErrorTotalPages = 1;

document.getElementById('line-error-search-form').addEventListener('submit', function (event) {
  event.preventDefault();
  lineErrorPage = 1;
  searchLineErrors();
});

document.getElementById('line-error-prev-btn').addEventListener('click', function () {
  if (lineErrorPage > 1) {
    lineErrorPage -= 1;
    fetchLineErrors();
  }
});

document.getElementById('line-error-next-btn').addEventListener('click', function () {
  if (lineErrorPage < lineErrorTotalPages) {
    lineErrorPage += 1;
    fetchLineErrors();
  }
});


/**
 * 폼에 입력된 필터 조건들을 모아서 lineErrorFilters에 저장하고 조회를 시작한다.
 * LineError는 150건뿐이라 조건이 하나도 없어도(=전체 조회) 막지 않는다.
 */
function searchLineErrors() {
  lineErrorFilters = {
    line_id: document.getElementById('le-filter-line-id').value,
    factory_id: document.getElementById('le-filter-factory-id').value,
    error_type: document.getElementById('le-filter-error-type').value,
    status: document.getElementById('le-filter-status').value,
    start: document.getElementById('le-start-date').value,
    end: document.getElementById('le-end-date').value,
  };
  fetchLineErrors();
}


/**
 * lineErrorFilters / lineErrorPage 기준으로 실제 API를 호출한다.
 */
function fetchLineErrors() {
  const statusMessage = document.getElementById('line-error-status-message');
  statusMessage.textContent = '라인 에러를 불러오는 중...';

  const params = new URLSearchParams();
  Object.entries(lineErrorFilters).forEach(function ([key, value]) {
    if (value !== '') params.append(key, value);
  });
  params.append('page', lineErrorPage);

  fetch('/api/errors/line/search?' + params.toString())
    .then(function (response) {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (result) {
      lineErrorPage = result.page;
      lineErrorTotalPages = result.total_pages;

      statusMessage.textContent = '조건에 맞는 라인 에러 총 ' + result.total_count
        + '건 중 ' + result.data.length + '건 표시 (마지막 갱신: '
        + new Date().toLocaleTimeString() + ')';

      renderLineErrorTable(result.data);
      updateLineErrorPaginationControls();
    })
    .catch(function (error) {
      console.error('라인 에러 조회 실패:', error);
      statusMessage.textContent = '라인 에러를 불러오지 못했습니다. (' + error.message + ')';
    });
}


function updateLineErrorPaginationControls() {
  const controls = document.getElementById('line-error-pagination-controls');
  const indicator = document.getElementById('line-error-page-indicator');
  const prevBtn = document.getElementById('line-error-prev-btn');
  const nextBtn = document.getElementById('line-error-next-btn');

  if (lineErrorTotalPages <= 1) {
    controls.style.display = 'none';
    return;
  }

  controls.style.display = '';
  indicator.textContent = lineErrorPage + ' / ' + lineErrorTotalPages + ' 페이지';
  prevBtn.disabled = (lineErrorPage <= 1);
  nextBtn.disabled = (lineErrorPage >= lineErrorTotalPages);
}


/**
 * 라인 에러 배열을 line-error-table-body에 <tr>로 그린다.
 */
function renderLineErrorTable(errors) {
  const tableBody = document.getElementById('line-error-table-body');
  tableBody.innerHTML = '';

  if (errors.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="5">조건에 맞는 라인 에러가 없습니다.</td></tr>';
    return;
  }

  errors.forEach(function (error) {
    const row = document.createElement('tr');
    if (error.is_pending) row.classList.add('row-alert');

    row.innerHTML =
      '<td>' + error.error_id + '</td>' +
      '<td>' + error.line_id + '</td>' +
      '<td>' + error.error_type + '</td>' +
      '<td>' + error.status + '</td>' +
      '<td>' + error.occurred_at + '</td>';

    tableBody.appendChild(row);
  });
}


// =============================================================
// 섹션 3. 로봇별 누적 에러 통계 (완료/미처리 구분 없는 전체 누적 집계 —
// 위 두 섹션과 달리 필터가 없는 참고용 정보라 맨 아래로 배치함)
// =============================================================

/**
 * /api/errors/stats/robot을 호출해서 통계 테이블을 채운다.
 * 데이터 예: [{robot_id: 1, total_count: 5}, {robot_id: 2, total_count: 12}, ...]
 */
function loadErrorStats() {
  const statusMessage = document.getElementById('stats-status-message');
  statusMessage.textContent = '통계를 불러오는 중...';

  fetch('/api/errors/stats/robot')
    .then(function (response) {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (data) {
      statusMessage.textContent = '총 ' + data.length + '대 로봇의 에러 기록';
      renderStatsTable(data);
    })
    .catch(function (error) {
      console.error('에러 통계 조회 실패:', error);
      statusMessage.textContent = '통계를 불러오지 못했습니다. (' + error.message + ')';
    });
}

/**
 * 통계 데이터 배열을 stats-table-body에 <tr>로 그린다.
 * 에러 건수가 많은 순(내림차순)으로 정렬해서 보여준다 —
 * "지금 가장 문제가 많은 로봇"이 위쪽에 오도록.
 */
function renderStatsTable(stats) {
  const tableBody = document.getElementById('stats-table-body');
  tableBody.innerHTML = '';

  if (stats.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="2">에러 기록이 없습니다.</td></tr>';
    return;
  }

  const sorted = stats.slice().sort(function (a, b) {
    return b.total_count - a.total_count;
  });

  sorted.forEach(function (stat) {
    const row = document.createElement('tr');

    if (stat.total_count >= 5) {
      row.classList.add('row-alert');
    }

    row.innerHTML =
      '<td>' + stat.robot_id + '</td>' +
      '<td>' + stat.total_count + '건</td>';

    tableBody.appendChild(row);
  });
}


// =============================================================
// 페이지 로드 시 세 섹션 모두 자동 실행 (화면에 보이는 순서대로)
// (RobotError 500건 / LineError 150건 — worklogs와 달리 소량이라
//  조건 없는 최초 조회도 안전함, robots 페이지와 동일한 이유)
// =============================================================
searchRobotErrors();
searchLineErrors();
loadErrorStats();