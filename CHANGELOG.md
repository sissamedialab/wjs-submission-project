# Changelog

## [2.1.1] - 2026-09-23

- fix: fix accessibily issue
- [specs#2981: Investigate possible bugs in submission and revision-submission related to cover-letter file](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2981) — fix(submission): stop orphaning/recreating the step1 cover-letter file on resubmit (!157)
- [specs#2983: Quality of life admin improvementrs](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2983) — Feat: advanced admin (!152)
- [specs#2984: As EO I want to create new files](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2984) — Feat: advanced admin (!152)
- [specs#3162: 17.9: 2nd Feedback JCAP & other journals' whole flow with Django 5.2](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3162) — Fix: set creator on Collaboration created in step4 (!158)
- [specs#2808: Drop JCOM-theme](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2808) — chore: drop dead BOOTSTRAP5 setting referencing JCOM-theme (!160)

## [2.1.0] - 2026-09-16

- [specs#2595: Migrate to Django 5.2](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2595) — Django 5.2 migration (!151)
- [specs#3155: Deploy to production](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3155) — Feature: change_article_license_rights management command (!142)
- [specs#2892: Align JCOM/JCOMAL license/rights fields for article from old submission](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2892) — Feature: change_article_license_rights management command (!142)
- [specs#3042: Drop key "affiliation" from revisionstorage.data and favor "affiliation_pk"](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3042) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3076: Submission - Revise metadata change specifications](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3076) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3083: 28.8 feedback - JCAP (and other journals) entire flow](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3083) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [wjs-help#190: revision submission errror (dev - 4220)](https://gitlab.sissamedialab.it/wjs/wjs-help/-/work_items/190) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#2782: Check Open Access Mode behaviour](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2782) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3074: Investigate "submission_requirements NOT set"](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3074) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#2729: Inconsistency in information update in step 8](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2729) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3097: Test Django 5.2](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3097) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3113: Verify that no Article has an "arXiv" DOI](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3113) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3119: Investigate missing "ControlledAffiliation" in step8](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3119) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3118: Investigate failed revision submission - step4 affiliation.pk](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3118) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#2979: 31 Jul feedback - Test JCAP whole review flow](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2979) — fix: correspondence author, affiliation and access-mode consistency in submission/revision steps 4, 7 and 8 (!128)
- [specs#3083: 28.8 feedback - JCAP (and other journals) entire flow](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3083) — fix: ensure special request updated it's not overwritten when editing step 7 (!153)
- No linked issue — Convert submission navigation markup to semantic ol/li (!155)
- [specs#3145: Ensure that corr.au without affiliation in JCOM can still submit/revision-submit](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3145) — Do not assume affiliation exists (!154)

## [2.0.19] - 2026-09-09

- [specs#2971: Analyse how to sync collaboration between tex and db](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2971) — Adapt Collaboration to tabellone (!147)

## [2.0.18] - 2026-09-09

- [specs#3054: Allow to modify access mode from advanced admin](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3054) — feat: allow editing access mode (!148)
- [specs#2918: JCAP corresponding author's required information](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2918) — refactor(account_validation): move jcom/jcap validators to wjs.jcom_profile (!150)
- [wjs-submission-project#30: Verify that wjs-submission does not depend from wjs-profile](https://gitlab.sissamedialab.it/wjs/wjs-submission-project/-/work_items/30) — refactor(account_validation): move jcom/jcap validators to wjs.jcom_profile (!150)

## [2.0.17] - 2026-08-26

- [wjs-help#205: JCOM_3682 - revision submission problem (step 7 - access)](https://gitlab.sissamedialab.it/wjs/wjs-help/-/work_items/205) — fix: fix inconsistencies in step 8 (!149)
- [specs#2042: JCAP / JHEP Submissions tests](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2042) — fix: fix inconsistencies in step 8 (!149)
- [specs#2979: 31 Jul feedback - Test JCAP whole review flow](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2979) — fix: fix inconsistencies in step 8 (!149)
- [specs#2977: 31 Jul feedback: JCAP settings and reminders for go-live](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2977) — fix: fix inconsistencies in step 8 (!149)
- [wjs-submission-project#31: Always add "article_data" to the context as a dictionary or as an instance in submission step-8](https://gitlab.sissamedialab.it/wjs/wjs-submission-project/-/work_items/31) — fix: fix inconsistencies in step 8 (!149)

## [2.0.16] - 2026-08-24

- [specs#2846: Investigate missing access mode in step-8](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2846) — fix: ensure missing step 7 does not break step8 (!133)
- [specs#2979: 31 Jul feedback - Test JCAP whole review flow](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2979) — fix: ensure missing step 7 does not break step8 (!133)
- [specs#2042: JCAP / JHEP Submissions tests](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2042) — fix: ensure disclaimer for access modes can be selected per journal (!132)
- [specs#2979: 31 Jul feedback - Test JCAP whole review flow](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2979) — fix: ensure disclaimer for access modes can be selected per journal (!132)
- No linked issue — Fix: improve error reporting for keyword / arxiv errors (!135)
- [specs#2042: JCAP / JHEP Submissions tests](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2042) — fix: fix typo (!130)

## [2.0.15] - 2026-08-14

- [specs#2879: Integrate hydra in wjs](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2879) — Relax dependencies (!145)

## [2.0.14] - 2026-08-12

- [specs#2784: Revisione accessibilità](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2784) — Bump dependencies (!144)

## [2.0.13] - 2026-08-12

- [wjs-profile-project#204: As developer I want to investigate why pytest 8.4 breaks our tests setup](https://gitlab.sissamedialab.it/wjs/wjs-profile-project/-/work_items/204) — chore(deps): bump pytest to 9.x, keep pytest-django capped below 4.13 (!139)
- [specs#3017: Ensure that step 2 (issue selection) fills primary_issue slot also](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3017) — Actually assign the projected issue to the article (!141)
- [wjs-help#201: JCOMAL_4314 - wrong issue assignation](https://gitlab.sissamedialab.it/wjs/wjs-help/-/work_items/201) — Actually assign the projected issue to the article (!141)
- [wjs-submission-project#30: Verify that wjs-submission does not depend from wjs-profile](https://gitlab.sissamedialab.it/wjs/wjs-submission-project/-/work_items/30) — Actually assign the projected issue to the article (!141)
- [specs#3033: Verify that wjs-submission does not depend from wjs-profile](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/3033) — Actually assign the projected issue to the article (!141)
- No linked issue — bugfix: fix das_display (!143)
- No linked issue — feat(a11y): add a11y review fixes (!110)
- No linked issue — docs: onboard Claude Code and align MR conventions with GitLab workflow (!140)

## [2.0.12] - 2026-08-06

- [wjs-profile-project#204: As developer I want to investigate why pytest 8.4 breaks our tests setup](https://gitlab.sissamedialab.it/wjs/wjs-profile-project/-/work_items/204) — chore: pin pytest / pytest-django (!136)
- [specs#2042: JCAP / JHEP Submissions tests](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2042) — fix: load article from kwargs instead of request.POST in DeleteFundingView (!131)
- [specs#2943: Internal Server Error: submission/4252/delete-funding/](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2943) — fix: load article from kwargs instead of request.POST in DeleteFundingView (!131)
- [wjs-submission-project#29: a new submission that I made did not have the A.section set](https://gitlab.sissamedialab.it/wjs/wjs-submission-project/-/work_items/29) — fix: load article from kwargs instead of request.POST in DeleteFundingView (!131)

## [2.0.11] - 2026-07-30

- [specs#2942: ensure submission step is not bumped if form validation fails](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2942) — Fix JCAP submission issues (!122)
- [specs#2042: JCAP / JHEP Submissions tests](https://gitlab.sissamedialab.it/wjs/specs/-/work_items/2042) — Fix JCAP submission issues (!122)
- Bump - Release 2.0.10.dev1
