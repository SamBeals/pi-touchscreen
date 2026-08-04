import QtQuick
import QtQuick.Layouts
import "../components"

ColumnLayout {
    spacing: Theme.gap
    anchors.fill: parent

    AppHeader {
        title: "Choose a product"
        showCart: true
        Layout.fillWidth: true
    }

    Text {
        text: App.browseStatus
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }

    PromoBanner {
        Layout.fillWidth: true
    }

    ProductGrid {
        Layout.fillWidth: true
        Layout.fillHeight: true
    }
}
