/*
  errors.js
  ──────────────────────────────────────────────────────────
  역할: errors.html 안의 두 섹션을 채운다.
    1. 로봇별 에러 통계  → GET /api/errors/stats/robot
    2. 미해결 에러 목록  → GET /api/errors/unresolved

  main.js와 구조는 완전히 동일한 패턴이다.
  (fetch → response.json() → 화면에 그리기)
  API가 2개라서 함수도 2세트로 나눠져 있을 뿐, 원리는 같다.
*/


// =============================================================
// 섹션 1. 로봇별 에러 통계
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

  // total_count 기준 내림차순 정렬 (원본 배열을 바꾸지 않도록 slice()로 복사 후 정렬)
  const sorted = stats.slice().sort(function (a, b) {
    return b.total_count - a.total_count;
  });

  sorted.forEach(function (stat) {
    const row = document.createElement('tr');

    // 에러가 5건 넘게 쌓인 로봇은 눈에 띄게 강조 (기준값은 임의로 정함, 필요시 조정)
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
// 섹션 2. 미해결 에러 목록
// =============================================================

/**
 * /api/errors/unresolved를 호출해서 미해결 에러 테이블을 채운다.
 * "새로고침" 버튼에서도 이 함수를 다시 호출한다.
 */
function loadUnresolvedErrors() {
  const statusMessage = document.getElementById('unresolved-status-message');
  statusMessage.textContent = '미해결 에러를 불러오는 중...';

  fetch('/api/errors/unresolved')
    .then(function (response) {
      if (!response.ok) {
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (data) {
      statusMessage.textContent = '미해결 에러 ' + data.length + '건 (마지막 갱신: ' + new Date().toLocaleTimeString() + ')';
      renderUnresolvedTable(data);
    })
    .catch(function (error) {
      console.error('미해결 에러 조회 실패:', error);
      statusMessage.textContent = '미해결 에러를 불러오지 못했습니다. (' + error.message + ')';
    });
}

/**
 * 미해결 에러 배열을 unresolved-table-body에 <tr>로 그린다.
 * error_service.py에서 is_pending 플래그가 이미 붙어서 오지만,
 * 이 API 특성상(status='pending'만 조회) 전부 true이므로
 * 모든 행을 동일하게 강조 표시한다.
 */
function renderUnresolvedTable(errors) {
  const tableBody = document.getElementById('unresolved-table-body');
  tableBody.innerHTML = '';

  if (errors.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="5">미해결 에러가 없습니다. 👍</td></tr>';
    return;
  }

  errors.forEach(function (error) {
    const row = document.createElement('tr');
    row.classList.add('row-alert');   // 전부 미해결이므로 전체 강조

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
// 페이지 로드 시 두 섹션 모두 자동 실행
// =============================================================
loadErrorStats();
loadUnresolvedErrors();