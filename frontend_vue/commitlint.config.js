/**
 * feat: add a new feature
 * fix: bug fix
 * docs: documentation update
 * style: code changes that do not affect program logic, such as whitespace, formatting, or missing semicolons
 * refactor: code refactoring that neither adds a feature nor fixes a bug
 * perf: performance or experience optimization
 * test: add new test cases or update existing ones
 * build: changes mainly related to the project build system, such as gulp, webpack, or rollup config
 * ci: changes mainly related to the continuous integration flow, such as Travis, Jenkins, GitLab CI, or Circle
 * chore: other changes that do not fit the categories above, such as build flow or dependency management
 * revert: revert an earlier commit
 */

module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore', 'revert']
    ],
    'subject-full-stop': [0, 'never'],
    'subject-case': [0, 'never']
  }
}
