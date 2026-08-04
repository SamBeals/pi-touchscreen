import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.sectionGap

        Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

        Image {
            visible: Theme.logoUrl.length > 0
            source: Theme.logoUrl
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredHeight: 96
            Layout.preferredWidth: parent.width * 0.5
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }

        Text {
            text: Theme.businessName
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.titleFontPx
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            text: Theme.attractHeadline
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.subtitleFontPx
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            visible: Theme.attractPromo.length > 0
            text: Theme.attractPromo
            color: Theme.accent
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodyFontPx
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        PromoBanner {
            Layout.fillWidth: true
        }

        Item { Layout.fillHeight: true; Layout.preferredHeight: 1 }

        PrimaryButton {
            text: "Start shopping"
            Layout.fillWidth: true
            onClicked: App.enterBrowse()
        }

        Item { Layout.fillHeight: true; Layout.preferredHeight: 1 }
    }

    MouseArea {
        anchors.fill: parent
        z: -1
        onClicked: App.enterBrowse()
    }

    Behavior on opacity {
        NumberAnimation { duration: Theme.animationMs }
    }
}
