# 우아레포츠 (wooaleports)

한국관광공사 TourAPI 국문 관광정보 v2(`B551011/KorService2`, 콘텐츠 유형 28=레포츠, 캠핑 AC05 제외 약 1.75천 곳)로 만든 레포츠 시설 정보 사이트(Python 정적 생성기). https://wooaleports.wooahouse.com — 캠핑은 우아캠프, 골프연습장·당구장 등 민간 체육시설은 우아레저.

- `scripts/fetch_data.py` — `areaBasedList2`로 목록, `detailIntro2`(이용시간·요금·휴무·개장기간·예약·주차·체험연령·문의)로 시설당 1호출 상세를 `data/details/{id//2000}.json.gz`에 **응답 필드 원래 이름 그대로** 누적(v2 필드명 미검증이라 빌더가 후보 이름 여러 개를 확인). 하루 예산 기본 300호출 — TourAPI 일일 한도 ~3,300을 코스·메뉴(2000)·숙소(1000)와 공유해 KST 06:00에 돈다. 메뉴 수집이 끝나면 예산을 늘릴 것.
- `scripts/build_site.py` — 상세가 30곳 미만이면 noindex '준비 중' 홈만 배포. 첫 실행 후 `data/details`를 열어 실제 필드명이 `FIELDS` 후보와 맞는지 확인할 것.
- Actions: push 시 빌드, 매일 KST 06:00 수집→커밋→빌드. 시크릿 `API_KEY`. 네이버 토큰은 `scripts/common.py` `NAVER_TOKEN`.
