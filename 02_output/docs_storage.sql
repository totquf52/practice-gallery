-- docs 버킷 허용 넣기
-- 화면(로그인 없는 손님 anon, 로그인한 사람 authenticated)이
-- docs 버킷에 문서를 올리고, 올라온 목록을 볼 수 있게 한다.
-- Supabase 의 SQL Editor 에 통째로 붙여 넣고 Run 을 누른다.
-- 몇 번을 다시 실행해도 오류 없이 같은 상태가 된다.

-- 1. docs 버킷이 없으면 만든다 (있으면 그대로 둔다)
--    public = true : 문서 주소만 알면 누구나 문서를 열어 볼 수 있다
insert into storage.buckets (id, name, public)
values ('docs', 'docs', true)
on conflict (id) do nothing;

-- 2. 전에 넣은 같은 이름의 허용을 지운다 (다시 실행할 때 겹쳐서 오류가 나지 않게)
drop policy if exists "docs 목록 보기" on storage.objects;
drop policy if exists "docs 올리기"   on storage.objects;

-- 3. docs 버킷 안에서만 목록 보기와 올리기를 허락한다
create policy "docs 목록 보기" on storage.objects
  for select to anon, authenticated
  using (bucket_id = 'docs');

create policy "docs 올리기" on storage.objects
  for insert to anon, authenticated
  with check (bucket_id = 'docs');

-- 4. 확인 : 결과에 세 줄(버킷 한 줄, 허용 두 줄)이 나오면 잘 들어간 것이다
--    (SQL Editor 는 마지막 결과 하나만 보여 줘서, 한 번에 보이게 묶었다)
select '버킷' as 갈래, id as 이름, 'public = ' || public as 내용
from storage.buckets
where id = 'docs'
union all
select '허용', policyname, cmd || ' / ' || array_to_string(roles, ', ')
from pg_policies
where schemaname = 'storage'
  and tablename = 'objects'
  and policyname in ('docs 목록 보기', 'docs 올리기');
