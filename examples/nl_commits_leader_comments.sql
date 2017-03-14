-- Commits by non-leaders commented by the leader

create table leadership.nl_commits_leader_comments ENGINE=MyISAM AS
  select project_leaders.project_id as project_id,
    count(*) as n

  from leadership.project_leaders

  left join leadership.yearly_commits
  on yearly_commits.project_id = project_leaders.project_id

  left join leadership.yearly_commit_comments
  on yearly_commits.id = yearly_commit_comments.commit_id

  where yearly_commit_comments.user_id = project_leaders.user_id and
    yearly_commits.author_id != project_leaders.user_id

  group by project_leaders.project_id;

alter table leadership.nl_commits_leader_comments add index(project_id);
