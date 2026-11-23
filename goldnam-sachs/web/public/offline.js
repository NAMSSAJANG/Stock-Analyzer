const lastViewed = localStorage.getItem('goldnam_last_viewed');
if (lastViewed && !Number.isNaN(Date.parse(lastViewed))) {
  document.getElementById('last-viewed').textContent = `마지막 조회 시각: ${new Date(lastViewed).toLocaleString('ko-KR')}`;
}
