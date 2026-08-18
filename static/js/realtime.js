// =============================================================================
// realtime.js
// 역할: 3개 페이지(로봇/에러/워크로그)에 공통으로 로드되는 실시간 알림 스크립트
// - socket.io-client로 서버와 WebSocket 연결
// - 네비게이션 바의 공장 선택 드롭다운 + 알림 벨을 제어
// - 서버(error_service.py)가 'robot_error' 이벤트를 보내면 알림 목록에 추가
// =============================================================================

(function () {

  // -------------------------------------------------------------------
  // 1. 공장 선택 상태 관리
  // - 아직 로그인 기능이 없어서, 어느 공장 관리자인지 localStorage로 임시 관리
  // - 나중에 Admin 로그인 붙이면 이 부분만 세션 기반으로 교체하면 됨
  // -------------------------------------------------------------------
  const FACTORY_STORAGE_KEY = 'selected_factory_id';

  function getSelectedFactoryId() {
    return localStorage.getItem(FACTORY_STORAGE_KEY) || '1'; // 기본값: 서울공장
  }

  function setSelectedFactoryId(factoryId) {
    localStorage.setItem(FACTORY_STORAGE_KEY, factoryId);
  }

  // -------------------------------------------------------------------
  // 2. 알림 목록 상태 (페이지 이동하면 초기화됨 — 새로고침 시 서버에 저장된
  //    이력을 불러오는 기능은 나중 단계에서 필요하면 추가)
  // -------------------------------------------------------------------
  let notifications = [];
  let unreadCount = 0;

  function renderBadge() {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
    badge.style.display = unreadCount > 0 ? 'flex' : 'none';
  }

  function renderNotifList() {
    const list = document.getElementById('notif-list');
    if (!list) return;

    if (notifications.length === 0) {
      list.innerHTML = '<li class="notif-empty">알림 없음</li>';
      return;
    }

    list.innerHTML = notifications
      .map(n => `
        <li class="notif-item">
          <strong>로봇 #${n.robot_id}</strong> — ${n.error_type}
          <span class="notif-time">${n.time}</span>
        </li>
      `)
      .join('');
  }

  function addNotification(data) {
    const time = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    notifications.unshift({ ...data, time });
    notifications = notifications.slice(0, 20); // 최근 20건까지만 메모리에 유지
    unreadCount += 1;
    renderBadge();
    renderNotifList();
  }

  // -------------------------------------------------------------------
  // 3. 소켓 연결
  // - io()는 socket.io.min.js(CDN)가 먼저 로드되어야 전역으로 사용 가능
  // - query.factory_id → 서버 socket_events.py의 connect 핸들러가 이 값으로
  //   join_room(f"factory_{factory_id}") 처리함
  // -------------------------------------------------------------------
  function connectSocket() {
    const factoryId = getSelectedFactoryId();
    const socket = io({ query: { factory_id: factoryId } });

    socket.on('connect', () => {
      console.log(`소켓 연결됨 (factory_id=${factoryId})`);
    });

    socket.on('disconnect', () => {
      console.log('소켓 연결 종료됨');
    });

    // error_service.py의 socketio.emit('robot_error', ...) 수신
    socket.on('robot_error', (data) => {
      console.log('새 에러 알림 수신:', data);
      addNotification(data);
    });
  }

  // -------------------------------------------------------------------
  // 4. UI 이벤트 바인딩
  // -------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    // 공장 선택 드롭다운
    const factorySelect = document.getElementById('factory-select');
    if (factorySelect) {
      factorySelect.value = getSelectedFactoryId();
      factorySelect.addEventListener('change', (e) => {
        setSelectedFactoryId(e.target.value);
        // 공장을 바꾸면 room도 새로 join해야 하므로 새로고침이 가장 확실함
        location.reload();
      });
    }

    // 알림 벨 클릭 → 드롭다운 토글 + 읽음 처리
    const bellBtn = document.getElementById('notif-bell');
    const dropdown = document.getElementById('notif-dropdown');
    if (bellBtn && dropdown) {
      bellBtn.addEventListener('click', () => {
        dropdown.classList.toggle('open');
        if (dropdown.classList.contains('open')) {
          unreadCount = 0;
          renderBadge();
        }
      });

      document.addEventListener('click', (e) => {
        if (!bellBtn.contains(e.target) && !dropdown.contains(e.target)) {
          dropdown.classList.remove('open');
        }
      });
    }

    renderBadge();
    renderNotifList();
    connectSocket();
  });

})(); 