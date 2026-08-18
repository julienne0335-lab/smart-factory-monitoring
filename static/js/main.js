/*
  main.js
  ──────────────────────────────────────────────────────────
  역할: /robots API를 호출해서 받아온 로봇 목록을
        index.html의 <tbody id="robot-table-body"> 안에
        <tr> 행으로 그려 넣는다.

  흐름:
    1. loadRobots() 함수 정의
    2. fetch('/robots')로 GET 요청 → Promise 반환
    3. .then(response => response.json())로 JSON 파싱
    4. .then(data => ...)에서 data(배열)를 순회하며 화면에 그림
    5. 페이지가 열리자마자 자동 실행되도록 맨 아래에서 한 번 호출
*/


/**
 * 로봇 목록을 서버에서 받아와 테이블에 그리는 함수.
 * - index.html의 "새로고침" 버튼에서도 이 함수를 다시 호출한다.
 */
function loadRobots() {
  const statusMessage = document.getElementById('status-message');
  const tableBody = document.getElementById('robot-table-body');

  // 로딩 중임을 사용자에게 알림 (선택 사항이지만 UX상 좋음)
  statusMessage.textContent = '로봇 목록을 불러오는 중...';

  // ------------------------------------------------------------------
  // fetch('/api/robots')
  // - robot.py의 @robot_bp.route('/robots') 라우트를 호출하는 것과 같다.
  // - app.py에서 register_blueprint(robot_bp, url_prefix='/api')로 등록되어
  //   있어서, 실제 주소는 '/robots'가 아니라 '/api/robots'이다.
  //   (url_prefix가 앞에 붙는다는 점 주의)
  // - fetch()는 기본적으로 GET 요청을 보낸다.
  // ------------------------------------------------------------------
  fetch('/api/robots')
    .then(function (response) {
      // response는 아직 "응답 자체"이지 데이터가 아니다.
      // response.json()을 호출해야 실제 JSON 데이터로 변환된다.
      // 이 변환 과정도 비동기이므로 다시 Promise를 반환 → .then() 한 번 더 필요.
      if (!response.ok) {
        // HTTP 상태코드가 200번대가 아니면 (예: 404, 500) 에러로 처리
        throw new Error('서버 응답 오류: ' + response.status);
      }
      return response.json();
    })
    .then(function (data) {
      // data는 robot_service.get_all_robots()가 반환한 배열 그대로다.
      // 예: [{robot_id: 1, model_name: "HR-200", line_id: 3,
      //       battery_level: 85, joint_wear: 12, status: "가동중",
      //       warning_threshold: 20, installed_at: "...", is_alert: false}, ...]

      statusMessage.textContent = '총 ' + data.length + '대 로봇 (마지막 갱신: ' + new Date().toLocaleTimeString() + ')';

      renderRobotTable(data);
    })
    .catch(function (error) {
      // fetch 자체가 실패했거나(네트워크 오류), 위에서 throw한 에러를 여기서 잡는다.
      console.error('로봇 목록 조회 실패:', error);
      statusMessage.textContent = '로봇 목록을 불러오지 못했습니다. (' + error.message + ')';
    });
}


/**
 * 로봇 배열을 받아서 테이블 tbody 안에 <tr> 행들을 그려 넣는 함수.
 * loadRobots()에서 데이터를 받아온 후 호출된다.
 *
 * @param {Array} robots - 로봇 객체 배열
 */
function renderRobotTable(robots) {
  const tableBody = document.getElementById('robot-table-body');

  // -----------------------------------------------------------------
  // 매번 새로 그리기 전에 기존 내용을 비운다.
  // (새로고침 버튼을 여러 번 눌러도 행이 계속 쌓이지 않도록)
  // -----------------------------------------------------------------
  tableBody.innerHTML = '';

  // 로봇이 하나도 없는 경우 (빈 배열)
  if (robots.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="6">등록된 로봇이 없습니다.</td></tr>';
    return;
  }

  // -----------------------------------------------------------------
  // forEach로 배열의 로봇 하나하나에 대해 <tr> 행을 만든다.
  // -----------------------------------------------------------------
  robots.forEach(function (robot) {

    // robot_service.py에서 status === '오류정지'인 로봇에 is_alert: true를
    // 붙여서 내려주므로, 프론트는 그 값을 그대로 사용하면 된다.
    // (이전에는 프론트에서 status를 직접 비교했지만, 백엔드 로직이
    //  고쳐졌으므로 백엔드가 계산한 결과를 신뢰하고 그대로 쓰는 것이 맞다.
    //  판정 기준이 바뀌어도 프론트 코드를 다시 고칠 필요가 없어짐)
    const isError = robot.is_alert;

    // <tr> 요소를 자바스크립트로 직접 생성
    const row = document.createElement('tr');

    // 오류 상태인 로봇 행에는 CSS 클래스를 붙여서 빨갛게 강조 (style.css에서 정의)
    if (isError) {
      row.classList.add('row-alert');
    }

    // template literal(백틱 `...`)로 <td> 6개를 한 번에 채운다.
    // robot 객체의 키 이름은 DB 컬럼명과 동일하다: robot_id, model_name,
    // line_id, battery_level, joint_wear, status
    row.innerHTML =
      '<td>' + robot.robot_id + '</td>' +
      '<td>' + robot.model_name + '</td>' +
      '<td>' + robot.line_id + '</td>' +
      '<td>' + robot.battery_level + '%</td>' +
      '<td>' + robot.joint_wear + '%</td>' +
      '<td>' + robot.status + (isError ? ' ⚠️' : '') + '</td>';

    // 완성된 행을 tbody에 추가
    tableBody.appendChild(row);
  });
}


// ----------------------------------------------------------------------
// 페이지가 열리자마자 자동으로 한 번 실행되도록 즉시 호출.
// (사용자가 "새로고침" 버튼을 누르지 않아도 처음엔 데이터가 바로 보여야 하므로)
// ----------------------------------------------------------------------
loadRobots();