-- Number of commits that have comments per project

create table leadership.commits_with_comments AS
  select project_commits.project_id as project_id,
    count(*) as n

  from (
    select distinct project_leaders.project_id, yearly_commits.id
    from leadership.project_leaders

    left join leadership.yearly_commits
    on yearly_commits.project_id = project_leaders.project_id

    inner join leadership.yearly_commit_comments
    on yearly_commits.id = yearly_commit_comments.commit_id

  ) as project_commits

  group by project_commits.project_id;
