/*
  main.js
  ──────────────────────────────────────────────────────────
  역할: /api/robots/search를 호출해서 필터 조건에 맞는 로봇 목록을
        index.html의 <tbody id="robot-table-body"> 안에 <tr> 행으로 그려 넣는다.

  흐름:
    1. 페이지가 열리면 조건 없이(=전체 75대) 자동 조회
    2. "검색" 버튼 → 폼의 필터 조건을 모아서 1페이지부터 재조회
    3. "이전/다음" 버튼 → 필터는 그대로 두고 페이지만 이동

  worklogs.js와 같은 패턴을 씀 (currentFilters/currentPage 상태 저장,
  pagination-controls/page-indicator 갱신 등) — 코드 스타일을 프로젝트
  전체에서 통일하기 위함.
*/

let currentFilters = {};
let currentPage = 1;
let currentTotalPages = 1;


document.getElementById('robot-search-form').addEventListener('submit', function (event) {
  event.preventDefault();   // 페이지 새로고침 방지
  currentPage = 1;          // 새로 검색하면 항상 1페이지부터
  searchRobots();
});

document.getElementById('prev-page-btn').addEventListener('click', function () {
  if (currentPage > 1) {
    currentPage -= 1;
    fetchRobots();
  }
});

document.getElementById('next-page-btn').addEventListener('click', function () {
  if (currentPage < currentTotalPages) {
    currentPage += 1;
    fetchRobots();
  }
});


/**
 * 폼에 입력된 필터 조건들을 모아서 currentFilters에 저장하고 조회를 시작한다.
 * 로봇은 75대뿐이라 조건이 하나도 없어도(=전체 조회) 막지 않는다.
 */
function searchRobots() {
  currentFilters = {
    robot_id: document.getElementById('filter-robot-id').value,
    line_id: document.getElementById('filter-line-id').value,
    factory_id: document.getElementById('filter-factory-id').value,
    status: document.getElementById('filter-status').value,
    max_battery: document.getElementById('filter-max-battery').value,
    min_joint_wear: document.getElementById('filter-min-joint-wear').value,
  };
  fetchRobots();
}


/**
 * currentFilters / currentPage 기준으로 실제 API를 호출한다.
 * "검색" 버튼과 "이전/다음" 버튼이 공통으로 이 함수를 호출한다.
 */
function fetchRobots() {
  const statusMessage = document.getElementById('status-message');
  statusMessage.textContent = '로봇 목록을 불러오는 중...';

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

  fetch('/api/robots/search?' + params.toString())
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

      statusMessage.textContent = '조건에 맞는 로봇 총 ' + result.total_count
        + '대 중 ' + result.data.length + '대 표시 (마지막 갱신: '
        + new Date().toLocaleTimeString() + ')';

      renderRobotTable(result.data);
      updatePaginationControls();
    })
    .catch(function (error) {
      console.error('로봇 목록 조회 실패:', error);
      statusMessage.textContent = '로봇 목록을 불러오지 못했습니다. (' + error.message + ')';
    });
}


/**
 * "이전/다음" 버튼과 "N / 전체M 페이지" 표시를 현재 상태에 맞게 갱신한다.
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
 * 로봇 배열을 받아서 테이블 tbody 안에 <tr> 행들을 그려 넣는 함수.
 * (기존과 동일 — is_alert는 service 계층에서 계산되어 옴)
 *
 * @param {Array} robots - 로봇 객체 배열
 */
function renderRobotTable(robots) {
  const tableBody = document.getElementById('robot-table-body');
  tableBody.innerHTML = '';

  if (robots.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="6">조건에 맞는 로봇이 없습니다.</td></tr>';
    return;
  }

  robots.forEach(function (robot) {
    const isError = robot.is_alert;
    const row = document.createElement('tr');

    if (isError) {
      row.classList.add('row-alert');
    }

    row.innerHTML =
      '<td>' + robot.robot_id + '</td>' +
      '<td>' + robot.model_name + '</td>' +
      '<td>' + robot.line_id + '</td>' +
      '<td>' + robot.battery_level + '%</td>' +
      '<td>' + robot.joint_wear + '%</td>' +
      '<td>' + robot.status + (isError ? ' ⚠️' : '') + '</td>';

    tableBody.appendChild(row);
  });
}


// ----------------------------------------------------------------------
// 페이지가 열리자마자 조건 없이(=전체) 자동 조회.
// (로봇은 75대뿐이라 워크로그와 달리 조건 없는 최초 조회가 안전함)
// ----------------------------------------------------------------------
searchRobots();