-- submissions 표 만들기 (실습 게시판에 올라오는 글을 담는 표)
-- Supabase 의 SQL Editor 에 통째로 붙여 넣고 Run 을 누른다.
-- 표가 이미 있으면 건드리지 않으므로, 다시 실행해도 올라온 글은 지워지지 않는다.

-- 1. 표를 만든다
create table if not exists public.submissions (
  id          bigint generated always as identity primary key,  -- 줄 번호, 저절로 붙는다
  practice_no integer     not null check (practice_no >= 1),    -- 실습 번호
  author      text        not null,                             -- 별명
  content     text        not null,                             -- 글
  created_at  timestamptz not null default now()                -- 올린 때, 저절로 붙는다
);

-- 2. 화면(로그인 없는 손님 anon, 로그인한 사람 authenticated)이 읽고 넣을 수 있게 문을 연다
grant select, insert on public.submissions to anon, authenticated;

-- 3. 줄마다 허락을 따지는 장치(RLS)를 켜고, 읽기 · 넣기만 허락한다
alter table public.submissions enable row level security;

drop policy if exists "누구나 읽기" on public.submissions;
drop policy if exists "누구나 넣기" on public.submissions;
create policy "누구나 읽기" on public.submissions for select to anon, authenticated using (true);
create policy "누구나 넣기" on public.submissions for insert to anon, authenticated with check (true);

-- 4. Supabase 가 새 표를 바로 알아보게 한다
notify pgrst, 'reload schema';
