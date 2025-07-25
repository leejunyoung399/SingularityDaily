# ARC-AGI 영역에서의 분포 외 일반화: 실행 유도 신경 프로그램 합성과 테스트 시간 미세 조정 비교

**원제목:** Out-of-Distribution Generalization in the ARC-AGIDomain: Comparing Execution-Guided Neural Program Synthesis and Test-Time Fine-Tuning

**요약:** 본 연구는 ARC-AGI 도메인에서의 분포 외 일반화 문제를 다루며, 실행 유도 신경 프로그램 합성(EG-NPS)과 테스트 시간 미세 조정(TTFT) 방법을 비교 분석합니다. ARC-AGI는 구성적 일반화 능력을 평가하는 개방형 시각적 추론 문제 도메인으로,  훈련 데이터와 테스트 데이터 간의 엄격한 분리를 통해 과적합을 방지하고 진정한 일반화 능력을 평가합니다.  연구에서는 ARC-AGI에 적용 가능한 EG-NPS 알고리즘을 새롭게 구현하고,  새로운 DSL과 프로그램 문법을 제시했습니다.  EG-NPS, 비실행 유도 NPS, TTFT 세 가지 방법을 비교하는 통제된 실험을 통해 EG-NPS가 새로운 해결책을 구성하는 능력에서 다른 알고리즘들을 능가함을 확인했습니다.  실험 결과, TTFT의 성공은 주로 LLM이 직접 활용하지 못하는 분포 내 지식을 유도하는 데 기인함을 시사합니다.  기존의 NPS 연구들과 비교하여 EG-NPS의 우수성을 보였으며,  특히 실행 단계별로 다음 연산, 피연산자, 변수 제거 등을 예측하는 PCCoder와 같은 기존 연구를 바탕으로  ARC-AGI 도메인에 적용 가능하도록 구현하였습니다.  결론적으로, 본 연구는 EG-NPS가 ARC-AGI와 같은 복잡한 문제 해결에 효과적임을 보여주며,  향후 AGI 개발에 중요한 시사점을 제공합니다.

[원문 링크](https://arxiv.org/pdf/2507.15877)
