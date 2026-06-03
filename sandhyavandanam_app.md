# Sandhyavandanam coach

## Motivation 

Sandhya vandanam is a sacred brahminical ritual that all who are initiated must perform 3 times a day as per the details in https://dn790000.ca.archive.org/0/items/RigvedaSandhyavandanamEngV1/Rigveda-Sandhyavandanam-Eng-v1.pdf. In this case, I wish to build an app who is a coach or teacher or more appropriately a respectable and knowledgeable guru in the rites and rituals of sandhyavandanam as per the dravidian/tamil tradition. 

## Coach's role

In this case, the rigved sandhyavandanam is of interest. I would like you to design an app that walks one through the ritual steps and uses text-to-audio to pronounce the sanskrit mantras that are part of the ritual step by step and use an audio agent model to listen and either correct gently or move to the next step in the ritual. 

The app should initially exist as a terminal app that coaches one through the steps and gently and patiently helps people, especially new learners complete the ritual in their native language.

## Open models
I am keen on using open audio models either through ollama or LMStudio (if it is supported) and make sure that a person is able to complete the pratah (or morning) sandhya ritual as prescribed in the doc. The mantras are in sanskrit, so models that can clone my voice or use a guru like senior voice proficient in Sanskrit would work really well. Mantras must be clearly pronounced without mistake.

## Research

Do some digging and research on all the actions that one performs during sandhya and include those as well in the coach/guru's instructions to the student. Research on techniques to build good audio AI agents with audio models, common failure modes. Prefer high quality open source models for this task that are well established and also easy to run locally with high performance and perhaps even good libraries. Models must be good at discerning what the student says and reason with that to make this a functional app.

Also ensure that you put a deterministic framework around the 26 steps around the Rigveda sandhyavandanam ritual to be able to go from start to finish.

Do extensive online research and planning before any implementation. We will build a simple tui or console app only at first to focus on the overall goals.
