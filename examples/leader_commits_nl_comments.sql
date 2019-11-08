-- Commits by leaders commented by non-leaders

create table leadership.leader_commits_nl_comments AS
  select project_commits.project_id as project_id,
    count(*) as n

  from (
    select distinct project_leaders.project_id, yearly_commits.id
    from leadership.project_leaders

    left join leadership.yearly_commits
    on yearly_commits.project_id = project_leaders.project_id

    left join leadership.yearly_commit_comments
    on yearly_commits.id = yearly_commit_comments.commit_id

    where yearly_commits.author_id = project_leaders.user_id and
      yearly_commit_comments.user_id != project_leaders.user_id
  ) as project_commits

  group by project_commits.project_id;
