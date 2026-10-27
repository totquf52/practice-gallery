-- subscriptions 표 만들기
-- 바탕 자료 : data/76_subscriptions.csv (12줄)
-- Supabase 의 SQL Editor 에 통째로 붙여 넣고 Run 을 누른다.
-- 몇 번을 다시 실행해도 표를 지우고 새로 만들어서, 처음 12줄 상태로 돌아온다.

-- 1. 있던 표를 지운다 (다시 실행할 때 처음으로 돌아오게)
drop table if exists public.subscriptions cascade;

-- 2. 표를 새로 만든다
create table public.subscriptions (
  id          bigint generated always as identity primary key,  -- 줄 번호, 저절로 붙는다
  name        text    not null,                                 -- 구독 이름
  category    text    not null,                                 -- 갈래
  monthly_fee integer not null check (monthly_fee >= 0),        -- 한 달 요금(원)
  last_used   date                                              -- 마지막으로 쓴 날
);

-- 3. CSV 의 12줄을 넣는다
insert into public.subscriptions (name, category, monthly_fee, last_used) values
  ('영화 · 드라마 구독', '영상',     13500,  '2026-10-18'),
  ('음악 구독',          '음악',     10900,  '2026-10-20'),
  ('클라우드 저장공간',  '업무',     2400,   '2026-10-19'),
  ('헬스장',             '운동',     55000,  '2026-03-02'),
  ('신문 구독',          '읽을거리', 150000, '2026-10-21'),
  ('우유 배달',          '먹거리',   18000,  '2026-10-21'),
  ('정수기 렌털',        '생활',     23900,  '2026-10-21'),
  ('꽃 정기배송',        '생활',     19800,  '2026-09-28'),
  ('전자책 구독',        '읽을거리', 9900,   '2026-08-15'),
  ('반찬 정기배송',      '먹거리',   64000,  '2026-10-16'),
  ('커피 원두 정기배송', '먹거리',   17000,  '2026-10-12'),
  ('문서 작성 도구',     '업무',     8900,   '2026-10-22');

-- 4. 화면(로그인 없는 손님 anon, 로그인한 사람 authenticated)이 표에 손댈 수 있게 문을 연다
grant select, insert, update, delete on public.subscriptions to anon, authenticated;

-- 5. 줄마다 허락을 따지는 장치(RLS)를 켜고, 읽기 · 넣기 · 고치기 · 지우기를 모두 허락한다
alter table public.subscriptions enable row level security;

create policy "누구나 읽기"   on public.subscriptions for select to anon, authenticated using (true);
create policy "누구나 넣기"   on public.subscriptions for insert to anon, authenticated with check (true);
create policy "누구나 고치기" on public.subscriptions for update to anon, authenticated using (true) with check (true);
create policy "누구나 지우기" on public.subscriptions for delete to anon, authenticated using (true);
