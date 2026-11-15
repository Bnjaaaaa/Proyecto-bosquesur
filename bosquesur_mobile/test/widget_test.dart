import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:bosquesur_mobile/main.dart';

void main() {
  testWidgets('BosqueSurApp muestra pantalla de inicio de sesión', (WidgetTester tester) async {
    await tester.pumpWidget(const BosqueSurApp());

    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.byType(TextField), findsWidgets);
  });
}
