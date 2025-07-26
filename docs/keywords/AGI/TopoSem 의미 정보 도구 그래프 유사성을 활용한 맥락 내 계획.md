# TopoSem: 의미 정보 도구 그래프 유사성을 활용한 맥락 내 계획

**원제목:** TopoSem: In-context planning with semantically-informed tooling graph similarity

**요약:** 본 연구는 전자상거래 판매자를 위한 지능형 어시스턴트 설계의 어려움, 특히 추상적인 판매자 질의와 다수의 내부 도구 조정의 복잡성에 초점을 맞추고 있습니다.  연구진은 이 문제 해결을 위해 상황 내 계획(ICP) 접근 방식을 활용하였으나, 기존 ICP의 한계점인 효과적인 예시 선택 문제를 해결하기 위해 TopoSem이라는 새로운 프레임워크를 제안합니다. TopoSem은 API 실행 그래프의 위상적 거리와 API 페이로드의 의미적 차이를 동시에 고려하여 예시를 선택합니다.  대조 학습 기법을 활용하여 의미 있는 임베딩을 학습하고, 동적 클러스터링 메커니즘을 통해 예시 선택 과정의 노이즈와 중복성을 줄였습니다.  실험 결과, TopoSem은 기존 예시 선택 방법보다 계획 정확도와 일반화 성능이 훨씬 우수하며, 특히 복잡한 API 조정이 필요한 상황에서 그 효과가 더욱 두드러짐을 보였습니다.  이는 API 실행 그래프의 구조적 정보를 고려함으로써 LLM의 계획 성능을 향상시켰다는 것을 의미합니다.  결론적으로 TopoSem은 전자상거래 지능형 어시스턴트 개발에 있어 중요한 발전을 제시하며,  더욱 효율적이고 정확한 상황 내 계획을 가능하게 합니다.

[원문 링크](https://www.amazon.science/publications/toposem-in-context-planning-with-semantically-informed-tooling-graph-similarity)
