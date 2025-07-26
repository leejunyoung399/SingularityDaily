# ADMET 고려 약물 설계를 위한 DeBERTa 기반 SMILES 인코더

**원제목:** DeBERTa-Based SMILES Encoders for ADMET-AwareDrugDesign

**요약:** 본 연구는 다양한 데이터 유형을 통합하는 다중 모드 약물 발견 프레임워크에서 효과적인 화학 구조 표현을 위해 DeBERTa 기반 SMILES 인코더를 미세 조정하는 것을 목표로 합니다.  ZINC 기반 사전 학습된 DeBERTa 체크포인트를 이용하여 30만 개의 PubChem-ADMET 데이터셋으로 22개의 ADMET (흡수, 분포, 대사, 배설, 독성) 종점에 대한 다중 레이블 회귀 방식과 Focal MAE 손실 함수를 적용하여 학습을 수행했습니다.  그 결과, 16개의 TDC 벤치마크 작업에서 상위 10위 안에 들었으며, 생체 이용률 및 CYP2C9 기질과 같은 중요한 종점에서 14~30%의 성능 향상을 보였습니다.  BERT 및 RoBERTa 기반 인코더와 비교하여 높은 MLM 정확도 (89% 이상)를 유지하며 화학 언어 이해 능력을 효과적으로 보존했습니다.  ADMET 경로 길이 지표 분석을 통해 DeBERTa가 더욱 분리된 잠재 표현을 생성하여 특정 특성에 대한 분자 조작에 적합함을 확인했습니다.  결론적으로, 이 연구는 구조적 유창성과 예측 특수성 간의 균형을 효과적으로 맞춘 ADMET 인식 DeBERTa 인코더가 AI 기반 약물 설계의 다중 모드 파이프라인에 강력한 구성 요소로 활용될 수 있음을 보여줍니다.  본 연구의 성과는 향후 AI 기반 약물 설계에서 효율적인 약물 후보 물질 발굴에 기여할 것으로 기대됩니다.

[원문 링크](https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/687740c7728bf9025eae0bf8/original/de-ber-ta-based-smiles-encoders-for-admet-aware-drug-design.pdf)
