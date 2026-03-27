# High level overview

Design an application that helps to facilitate the creation of and curation of biomedical concepts in the CDISC Library.

The application should appear as close to that shown in the file `files/cdisc_bc_ai_platform.html`.

The application should be easy for each of the roles required for the curation process.

The `ncit-concept-resolver` can be used to assist in the curation process to review proposed additions of biomedical concepts to the CDISC Library as well as to determine the appropriate details to include in the Library.

Existing biomedical concepts and the correct JSON format can be accessed using the agent `cdisc-concept-explorer`.

The goal is to make the process of creating new biomedical concepts and the curation process easier and much quicker.

This corresponds to goal 1 described in `files/cdisc_smart_goals_infographic.html`.

Only the environment parameter `CDISC_API_KEY` should be used for authentication to the API.

The CDISC API for biomedical concepts is available here: https://api.library.cdisc.org/api/cosmos/v2.

Instructions for using the NCIT rest client API can be found here: https://github.com/NCIEVS/evsrestapi-client-SDK.

An example of Data element concept mappings is shown in the file `files/BC DEC Templates.xlsx`.

Review the files in the `files` directory.

Use the agent cdisc-frontend-dev to choose the best way in which to develop the web application but favor Jinja and Flask as the chosen implmentation.

Operate only in plan mode.

If unsure of anything, ask the user for clarification.

# Files to review
1. `files/BC Curation Principles and Completion GLs.xlsx` contains the rules and curation principles for adding biomedical concepts to the CDISC library which are accessible thorugh teh CDISC API
2. `files/BC Examples.xlsx` is an example of the file being used to create new biomedical concepts in the CDISC library.
3. `files/BC Curation Principles and Completion GLs.xlsx` describes the entire process.  This file should be reviewed first and the new application must adhere to the rules described in the worksheets of the file.
4. `files/BC DEC Templates.xlsx`
5. `files/BC Governance.docx` 
6. `files/BC DEC Templates.xlsx`



# Agents
1. cdisc-concept-explorer
2. ncit-concept-resolver
3. cdisc-frontend-dev
4. mike
