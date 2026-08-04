import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

ColumnLayout {
    spacing: Theme.sectionGap
    anchors.fill: parent

    AppHeader {
        showBrand: true
        showCart: true
        title: ""
        Layout.fillWidth: true
    }

    // Only surface operational gates — not inventory counts
    Rectangle {
        id: statusChip
        visible: {
            var s = App.browseStatus
            return s.indexOf("unavailable") >= 0
                || s.indexOf("stale") >= 0
                || s.indexOf("unreachable") >= 0
        }
        Layout.fillWidth: true
        Layout.preferredHeight: visible ? statusText.implicitHeight + 20 : 0
        radius: height / 2
        color: Theme.warningSurface
        border.color: Theme.warningBorder
        border.width: 1

        Text {
            id: statusText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 14
            text: App.browseStatus
            color: Theme.warning
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodyFontPx
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    PromoBanner {
        Layout.fillWidth: true
    }

    ProductGrid {
        Layout.fillWidth: true
        Layout.fillHeight: true
    }
}
