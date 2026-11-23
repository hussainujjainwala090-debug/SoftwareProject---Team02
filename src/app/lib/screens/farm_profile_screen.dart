import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../models.dart';
import '../state/session.dart';

/// UI-2: Farm profile and crop selection (FR-02). The location is set on the
/// map, from GPS, or typed in; it is later used for local weather.
class FarmProfileScreen extends StatefulWidget {
  const FarmProfileScreen({super.key, this.farm, this.showMap = true});
  final Farm? farm;

  /// Map tiles need the internet; widget tests turn the map off.
  final bool showMap;

  @override
  State<FarmProfileScreen> createState() => _FarmProfileScreenState();
}

class _FarmProfileScreenState extends State<FarmProfileScreen> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.farm?.name);
  late final _lat = TextEditingController(text: widget.farm?.latitude.toStringAsFixed(5));
  late final _lon = TextEditingController(text: widget.farm?.longitude.toStringAsFixed(5));
  late final Set<String> _crops = {...?widget.farm?.crops};
  final _map = MapController();
  bool _busy = false;
  String? _cropError;

  LatLng? get _point {
    final lat = double.tryParse(_lat.text), lon = double.tryParse(_lon.text);
    return lat == null || lon == null ? null : LatLng(lat, lon);
  }

  void _setPoint(LatLng p) {
    setState(() {
      _lat.text = p.latitude.toStringAsFixed(5);
      _lon.text = p.longitude.toStringAsFixed(5);
    });
  }

  Future<void> _useGps() async {
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        throw Exception('Location permission was not given. Set the pin on the map instead.');
      }
      final pos = await Geolocator.getCurrentPosition();
      final p = LatLng(pos.latitude, pos.longitude);
      _setPoint(p);
      if (widget.showMap) _map.move(p, 14);
    } on Object catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  String? _coord(String? v, int limit) {
    final d = double.tryParse(v ?? '');
    if (d == null) return 'Required';
    if (d < -limit || d > limit) return 'Must be between -$limit and $limit';
    return null;
  }

  Future<void> _save() async {
    setState(() => _cropError = _crops.isEmpty ? 'Tick at least one crop' : null);
    if (!_form.currentState!.validate() || _crops.isEmpty) return;
    setState(() => _busy = true);
    try {
      await context.read<Session>().saveFarm(
            farmId: widget.farm?.farmId,
            name: _name.text.trim(),
            latitude: double.parse(_lat.text),
            longitude: double.parse(_lon.text),
            crops: _crops.toList()..sort(),
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Farm profile saved')));
        if (Navigator.of(context).canPop()) Navigator.of(context).pop();
      }
    } on Object catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final point = _point;
    return Scaffold(
      appBar: AppBar(title: const Text('Farm profile')),
      body: Form(
        key: _form,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          TextFormField(
            key: const Key('farmName'),
            controller: _name,
            decoration: const InputDecoration(
                labelText: 'Farm name', hintText: 'e.g. Al Ain palm farm', border: OutlineInputBorder()),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Farm name is required' : null,
          ),
          const SizedBox(height: 16),
          Text('Farm location', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          if (widget.showMap)
            SizedBox(
              height: 200,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: FlutterMap(
                  mapController: _map,
                  options: MapOptions(
                    initialCenter: point ?? const LatLng(24.2075, 55.7447), // Al Ain
                    initialZoom: point == null ? 8 : 13,
                    onTap: (_, p) => _setPoint(p),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'ae.adu.swe401.agriscan',
                    ),
                    if (point != null)
                      MarkerLayer(markers: [
                        Marker(point: point, child: const Icon(Icons.location_pin, color: Colors.red, size: 36)),
                      ]),
                    const SimpleAttributionWidget(source: Text('OpenStreetMap contributors')),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextFormField(
                key: const Key('lat'),
                controller: _lat,
                keyboardType: const TextInputType.numberWithOptions(signed: true, decimal: true),
                decoration: const InputDecoration(labelText: 'Latitude', border: OutlineInputBorder()),
                validator: (v) => _coord(v, 90),
                onChanged: (_) => setState(() {}),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextFormField(
                key: const Key('lon'),
                controller: _lon,
                keyboardType: const TextInputType.numberWithOptions(signed: true, decimal: true),
                decoration: const InputDecoration(labelText: 'Longitude', border: OutlineInputBorder()),
                validator: (v) => _coord(v, 180),
                onChanged: (_) => setState(() {}),
              ),
            ),
          ]),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.my_location),
            label: const Text('Use my current location'),
            onPressed: _useGps,
          ),
          const SizedBox(height: 16),
          Text('Crops grown', style: Theme.of(context).textTheme.titleSmall),
          Wrap(spacing: 8, children: [
            for (final e in cropLabels.entries)
              FilterChip(
                label: Text(e.value),
                selected: _crops.contains(e.key),
                onSelected: (on) => setState(() => on ? _crops.add(e.key) : _crops.remove(e.key)),
              ),
          ]),
          if (_cropError != null)
            Text(_cropError!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _busy ? null : _save,
            child: Text(_busy ? 'Saving...' : 'Save farm profile'),
          ),
        ]),
      ),
    );
  }
}
