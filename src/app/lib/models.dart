// Data classes for the backend's JSON (field names follow the data design, DB-1).

double? _d(Object? v) => v == null ? null : (v as num).toDouble();

class AppUser {
  AppUser({required this.userId, required this.name, required this.email, required this.role,
      this.disabled = false});

  factory AppUser.fromJson(Map<String, dynamic> j) => AppUser(
        userId: j['user_id'] as String,
        name: j['name'] as String,
        email: j['email'] as String,
        role: j['role'] as String,
        disabled: (j['disabled'] as bool?) ?? false,
      );

  final String userId;
  final String name;
  final String email;
  final String role;
  final bool disabled;

  bool get isAdmin => role == 'admin';
  bool get isAgronomist => role == 'agronomist';
  bool get canScan => role == 'farmer' || role == 'farm_owner' || role == 'admin';
}

class Farm {
  Farm({required this.farmId, required this.ownerId, required this.name, required this.latitude,
      required this.longitude, required this.crops});

  factory Farm.fromJson(Map<String, dynamic> j) => Farm(
        farmId: j['farm_id'] as String,
        ownerId: j['owner_id'] as String,
        name: j['name'] as String,
        latitude: _d(j['latitude'])!,
        longitude: _d(j['longitude'])!,
        crops: (j['crops'] as List).cast<String>(),
      );

  final String farmId;
  final String ownerId;
  final String name;
  final double latitude;
  final double longitude;
  final List<String> crops;
}

class Treatment {
  Treatment({required this.type, required this.guidance, required this.safetyWarning});

  factory Treatment.fromJson(Map<String, dynamic> j) => Treatment(
        type: j['type'] as String,
        guidance: j['guidance'] as String,
        safetyWarning: j['safety_warning'] as String,
      );

  final String type; // organic | chemical | preventive
  final String guidance;
  final String safetyWarning;

  Map<String, dynamic> toJson() => {'type': type, 'guidance': guidance, 'safety_warning': safetyWarning};
}

class WeatherInfo {
  WeatherInfo({required this.available, this.notice, this.temperature, this.humidity, this.rainfall});

  factory WeatherInfo.fromJson(Map<String, dynamic> j) => WeatherInfo(
        available: j['available'] as bool,
        notice: j['notice'] as String?,
        temperature: _d(j['temperature']),
        humidity: _d(j['humidity']),
        rainfall: _d(j['rainfall']),
      );

  final bool available;
  final String? notice;
  final double? temperature;
  final double? humidity;
  final double? rainfall;

  String get summary => available
      ? '${temperature!.toStringAsFixed(0)} °C, humidity ${humidity!.toStringAsFixed(0)}%, '
          'rain ${rainfall!.toStringAsFixed(1)} mm'
      : 'Weather unavailable';
}

class Diagnosis {
  Diagnosis({
    required this.diagnosisId,
    required this.farmId,
    required this.cropType,
    required this.capturedAt,
    required this.label,
    required this.status,
    required this.confidence,
    this.diseaseId,
    this.affectedAreaPct,
    this.severityLevel,
    this.spreadRisk,
    this.spreadRiskExplanation,
    this.imageUrl,
    this.overlayUrl,
    this.reviewedBy,
    this.advice,
    this.weather,
    this.treatments = const [],
    this.feedbackCorrect,
  });

  factory Diagnosis.fromJson(Map<String, dynamic> j) => Diagnosis(
        diagnosisId: j['diagnosis_id'] as String,
        farmId: j['farm_id'] as String,
        cropType: j['crop_type'] as String,
        capturedAt: DateTime.parse(j['captured_at'] as String),
        label: j['label'] as String,
        status: j['status'] as String,
        confidence: _d(j['confidence'])!,
        diseaseId: j['disease_id'] as String?,
        affectedAreaPct: _d(j['affected_area_pct']),
        severityLevel: j['severity_level'] as String?,
        spreadRisk: j['spread_risk'] as String?,
        spreadRiskExplanation: j['spread_risk_explanation'] as String?,
        imageUrl: j['image_url'] as String?,
        overlayUrl: j['overlay_url'] as String?,
        reviewedBy: j['reviewed_by'] as String?,
        advice: j['advice'] as String?,
        weather: j['weather'] == null ? null : WeatherInfo.fromJson(j['weather'] as Map<String, dynamic>),
        treatments: ((j['treatments'] as List?) ?? const [])
            .map((t) => Treatment.fromJson(t as Map<String, dynamic>))
            .toList(),
        feedbackCorrect: (j['feedback'] as Map<String, dynamic>?)?['correct'] as bool?,
      );

  final String diagnosisId;
  final String farmId;
  final String cropType;
  final DateTime capturedAt;
  final String label;
  final String status; // confirmed | uncertain
  final double confidence;
  final String? diseaseId;
  final double? affectedAreaPct;
  final String? severityLevel;
  final String? spreadRisk;
  final String? spreadRiskExplanation;
  final String? imageUrl;
  final String? overlayUrl;
  final String? reviewedBy;
  final String? advice;
  final WeatherInfo? weather;
  final List<Treatment> treatments;
  final bool? feedbackCorrect;

  bool get isUncertain => status == 'uncertain';
}

class SpreadRiskInfo {
  SpreadRiskInfo({this.level, required this.explanation, required this.weather});

  factory SpreadRiskInfo.fromJson(Map<String, dynamic> j) => SpreadRiskInfo(
        level: j['spread_risk'] as String?,
        explanation: j['explanation'] as String,
        weather: WeatherInfo.fromJson(j['weather'] as Map<String, dynamic>),
      );

  final String? level;
  final String explanation;
  final WeatherInfo weather;
}

class Disease {
  Disease({required this.diseaseId, required this.name, required this.cropType, this.symptoms,
      required this.archived, required this.treatments});

  factory Disease.fromJson(Map<String, dynamic> j) => Disease(
        diseaseId: j['disease_id'] as String,
        name: j['name'] as String,
        cropType: j['crop_type'] as String,
        symptoms: j['symptoms'] as String?,
        archived: j['archived'] as bool,
        treatments: (j['treatments'] as List)
            .map((t) => Treatment.fromJson(t as Map<String, dynamic>))
            .toList(),
      );

  final String diseaseId;
  final String name;
  final String cropType;
  final String? symptoms;
  final bool archived;
  final List<Treatment> treatments;
}

class Report {
  Report({required this.reportId, required this.pdfUrl, required this.createdAt});

  factory Report.fromJson(Map<String, dynamic> j) => Report(
        reportId: j['report_id'] as String,
        pdfUrl: j['pdf_url'] as String,
        createdAt: DateTime.parse(j['created_at'] as String),
      );

  final String reportId;
  final String pdfUrl;
  final DateTime createdAt;
}

class WeekCount {
  WeekCount(this.week, this.scans, this.avgAffectedAreaPct);
  final String week;
  final int scans;
  final double? avgAffectedAreaPct;
}

class Dashboard {
  Dashboard({required this.totalScans, required this.diseasesFound, required this.uncertain,
      required this.scansPerWeek, required this.commonDiseases, required this.climateAlert});

  factory Dashboard.fromJson(Map<String, dynamic> j) => Dashboard(
        totalScans: j['total_scans'] as int,
        diseasesFound: j['diseases_found'] as int,
        uncertain: j['uncertain'] as int,
        scansPerWeek: (j['scans_per_week'] as List)
            .map((w) => WeekCount(w['week'] as String, w['scans'] as int, _d(w['avg_affected_area_pct'])))
            .toList(),
        commonDiseases: {
          for (final d in j['common_diseases'] as List) d['disease'] as String: d['count'] as int,
        },
        climateAlert: SpreadRiskInfo.fromJson(j['climate_alert'] as Map<String, dynamic>),
      );

  final int totalScans;
  final int diseasesFound;
  final int uncertain;
  final List<WeekCount> scansPerWeek;
  final Map<String, int> commonDiseases;
  final SpreadRiskInfo climateAlert;
}

class ModelAccuracy {
  ModelAccuracy({required this.totalFeedback, this.overallAccuracy, required this.weeks});

  factory ModelAccuracy.fromJson(Map<String, dynamic> j) => ModelAccuracy(
        totalFeedback: j['total_feedback'] as int,
        overallAccuracy: _d(j['overall_accuracy']),
        weeks: (j['weeks'] as List)
            .map((w) => (week: w['week'] as String, feedback: w['feedback'] as int,
                accuracy: _d(w['accuracy'])!))
            .toList(),
      );

  final int totalFeedback;
  final double? overallAccuracy;
  final List<({String week, int feedback, double accuracy})> weeks;
}
