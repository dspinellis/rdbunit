-- Number of commits that have comments per project

select project_leaders.project_id as project_id,
  coalesce(nl_commits_leader_comments.n, 0) as nl_commits_leader_comments,
  coalesce(leader_commits_nl_comments.n, 0) as leader_commits_nl_comments,
  coalesce(nl_issues_leader_comments.n, 0) as nl_issues_leader_comments,
  coalesce(leader_issues_nl_comments.n, 0) as leader_issues_nl_comments,
  coalesce(commits_with_comments.n, 0) as commits_with_comments,
  coalesce(issues_with_comments.n, 0) as issues_with_comments

  from leadership.project_leaders

  left join leadership.nl_commits_leader_comments
  on project_leaders.project_id = nl_commits_leader_comments.project_id

  left join leadership.leader_commits_nl_comments
  on project_leaders.project_id = leader_commits_nl_comments.project_id

  left join leadership.nl_issues_leader_comments
  on project_leaders.project_id = nl_issues_leader_comments.project_id

  left join leadership.leader_issues_nl_comments
  on project_leaders.project_id = leader_issues_nl_comments.project_id

  left join leadership.commits_with_comments
  on project_leaders.project_id = commits_with_comments.project_id

  left join leadership.issues_with_comments
  on project_leaders.project_id = issues_with_comments.project_id;
